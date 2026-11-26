"""Procedural 90.0 s (100 BPM) trailer score + punchy diegetic SFX mixer.

    python tools/trailer_call/score.py                     # build outputs/trailer_call/score.wav
    python tools/trailer_call/score.py --music track.mp3   # external music + diegetic SFX

Preserves Call of Acaristan's Romanian-minor leitmotif while adding:
  - Dynamic sidechain ducking around explosions, gunfights, LMG bursts & pre-drop breaths.
  - Full audible diegetic SFX bed (crackling fire, footsteps, police siren, shotgun + pump,
    marble/steel ricochets, server arc zaps, heavy rotors, sniper crack -> title sub-drop).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if os.path.join(ROOT, "tools") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
if os.path.join(ROOT, "tools", "trailer3d") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "tools", "trailer3d"))

from ost import album as A  # noqa: E402
from ost import synth as S  # noqa: E402
import sfx as X  # noqa: E402

SR = S.SR                     # 44100 Hz
BPM = 100.0
BAR_S = 60.0 / BPM * 4.0      # 2.4 s per 4/4 bar
TOTAL = 90.0                  # 37.5 bars
OUT_DIR = os.path.join(ROOT, "outputs", "trailer_call")

BIG_HITS = (28.8, 57.6, 80.4)
SILENCE = (76.8, 80.4)        # The Breath: dead musical silence before title slam


def _decode_external(path: str) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    arr = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
    return arr.T


def _build_procedural_music() -> np.ndarray:
    """Compose the 90.0 s 100 BPM trailer suite from Call of Acaristan leitmotifs."""
    T = S.Track(38, BPM, beats=4, seed=2088, verb_s=3.4, damp=4300.0, tail=2.0, target_db=-15.5)

    # --- ACT I: Cold Open & Fallout (Bars 0..11, 0.0..28.8s) ----------------
    T.add(S.fade(S.drone(S.hz("E1"), T.dur(48)), 1.6, 0.6), 0.0, 0.22, 0.0, 0.25)
    A.tick(T, 0, 12, gain=0.062)
    A.motif(T, S.cello, A.CALL, "E3", 1, scale=1.5, gain=0.38, pan=-0.12, verb=0.55)
    A.motif(T, S.strings, A.ANSWER, "E4", 5, scale=1.0, gain=0.22, pan=0.18, verb=0.55, a=0.25)
    A.pads(T, S.organ, ["Em", "C", "Am", "B", "Em", "B"], 6, 0.19, verb=0.45, base=40)
    for b in range(8, 12):
        T.add(S.timpani(S.hz("E2"), b), T.t(b, 0), 0.24 + 0.08 * (b - 8), 0.0, 0.45)
        if b >= 10:
            T.add(S.timpani(S.hz("E2"), b + 10), T.t(b, 2), 0.26 + 0.06 * (b - 10), 0.0, 0.45)
    T.add(S.riser(T.dur(4)), T.t(11, 0), 0.30, 0.0, 0.35)

    # --- ACT II: Two Roads Escalation (Bars 12..23, 28.8..57.6s) ------------
    T.add(S.boom(31), T.t(12, 0), 0.78, 0.0, 0.55)
    T.add(S.braam(S.hz("E1"), T.dur(3.5)), T.t(12, 0), 0.32, 0.0, 0.45)
    A.state_band(T, 12, gain=0.88)
    A.motif(T, S.strings, A.FANFARE, "E3", 12, gain=0.30, verb=0.38, a=0.06)
    A.motif(T, S.brass, A.FANFARE, "E3", 16, gain=0.40, verb=0.32)
    for k in (0, 2):
        A.motif(T, S.pluck, A.RIFF, "E2", 16 + k, gain=0.22, pan=-0.28, verb=0.32, bright=0.65, twang=0.15)
    A.groove(T, 20, 4, [
        (S.kick, [0, 1, 2, 3], 0.50, 0.0, 0.08),
        (S.snare, [1, 3], 0.34, 0.0, 0.28),
        (A.low_taiko, [0, 2], 0.42, 0.0, 0.30),
    ])
    A.pads(T, S.choir, ["Em", "C", "D", "B"], 20, 0.25, base=52, verb=0.45)
    A.motif(T, S.brass, A.FANFARE[:8], "E4", 20, gain=0.38, verb=0.32)
    T.add(S.riser(T.dur(4)), T.t(23, 0), 0.34, 0.0, 0.35)

    # --- ACT III: Kinetic Climax (Bars 24..31, 57.6..76.8s) -----------------
    T.add(S.boom(32), T.t(24, 0), 0.85, 0.0, 0.55)
    T.add(S.braam(S.hz("E1"), T.dur(3.0)), T.t(24, 0), 0.36, 0.0, 0.45)
    A.state_band(T, 24, gain=1.02)
    A.pads(T, S.choir, A.STATE_E, 24, 0.28, base=52, verb=0.45)
    A.motif(T, S.brass, A.FANFARE, "E4", 24, gain=0.42, verb=0.30)
    A.motif(T, S.strings, A.FANFARE, "E5", 24, gain=0.28, verb=0.35, a=0.04)
    A.groove(T, 27, 3, [
        (A.low_taiko, [0, 1, 2, 3], 0.48, 0.0, 0.25),
        (A.high_taiko, [0.5, 1.5, 2.5, 3.5], 0.32, 0.25, 0.25),
        (S.snare, [0.5, 1, 2, 2.5, 3, 3.5], 0.28, 0.0, 0.24),
    ])
    A.motif(T, S.strings, A.CALL, "E4", 30, scale=0.75, gain=0.34, verb=0.35, a=0.04)
    A.motif(T, S.brass, A.UCILEV, "E4", 30, scale=0.75, gain=0.32, pan=-0.22, verb=0.35)
    T.add(S.riser(T.dur(8)), T.t(30, 0), 0.42, 0.0, 0.35)

    # --- TITLE SLAM & RESONANCE (80.4..90.0s, Bar 33.5..37.5) ---------------
    T.add(S.boom(33), 80.4, 0.94, 0.0, 0.65)
    T.add(S.braam(S.hz("E1"), 4.2), 80.4, 0.50, 0.0, 0.55)
    T.add(S.bell(S.hz("E3"), 3), 80.42, 0.26, -0.25, 0.70)
    T.add(S.fade(S.cello(S.hz("E2"), 7.5), 0.15, 3.2), 80.6, 0.34, 0.0, 0.60)
    T.add(S.fade(S.strings(S.hz("B2"), 7.2, a=0.6, r=2.8, cutoff=1400.0), 0.2, 3.0), 80.8, 0.22, 0.12, 0.65)
    T.add(S.bell(S.hz("E3"), 4), 85.2, 0.16, 0.22, 0.75)

    mix = T.render()
    n_tot = int(TOTAL * SR)
    if mix.shape[1] < n_tot:
        mix = np.pad(mix, ((0, 0), (0, n_tot - mix.shape[1])))
    else:
        mix = mix[:, :n_tot].copy()

    s0, s1 = int(SILENCE[0] * SR), int(SILENCE[1] * SR)
    ramp = int(0.035 * SR)
    mix[:, s0 - ramp:s0] *= np.linspace(1.0, 0.0, ramp)
    mix[:, s0:s1] = 0.0
    return mix


# ---------------------------------------------------------------------------
# Diegetic SFX Recipes (all deterministic via tools/trailer3d/sfx.py)
# ---------------------------------------------------------------------------

def _explosion(big=True):
    dur = 2.6 if big else 1.5
    n = int(dur * SR)
    sub = X.sine(lambda t: 32 + 72 * np.exp(-t * 7.2), n) * X.env_exp(n, 0.54 if big else 0.28, 0.003)
    roar = X.band(X.noise(n), 40, 860) * X.env_exp(n, 0.50 if big else 0.26, 0.006)
    debris = X.band(X.noise(n), 950, 5600) * X.env_exp(n, 0.26 if big else 0.14, 0.012) * 0.55
    crack = X.band(X.noise(n), 1800, 9500) * X.env_exp(n, 0.016) * 0.85
    return X.norm(sub * 1.45 + roar + debris + crack)


def _rifle_shot(variant: int = 0):
    """Dry, heavy tactical rifle crack (low-mid chest punch, zero metallic chirp)."""
    rng = np.random.default_rng(310 + variant * 47)
    p_mul = float(rng.uniform(0.92, 1.09))
    n = int(0.42 * SR)
    f_lo = 62.0 * p_mul
    thump = X.sine(lambda t: f_lo + 95.0 * p_mul * np.exp(-t * 30.0), n) * X.env_exp(n, 0.058, 0.001)
    bark = X.band(rng.standard_normal(n), 140.0 * p_mul, 2100.0 * p_mul) * X.env_exp(n, 0.036, 0.0015)
    snap = X.band(rng.standard_normal(n), 1100.0, 5200.0) * X.env_exp(n, 0.009, 0.0008) * 0.55
    tail = X.band(rng.standard_normal(n), 110.0, 1250.0) * X.env_exp(n, 0.14, 0.012) * 0.34
    return X.norm(thump * 1.35 + bark * 1.15 + snap + tail)


def _lmg_shot(variant: int = 0):
    """Deep, dry 7.62mm heavy LMG thump with pitch-varied takes (no bright hiss)."""
    rng = np.random.default_rng(520 + variant * 53)
    p_mul = float(rng.uniform(0.93, 1.08))
    n = int(0.32 * SR)
    f_lo = 58.0 * p_mul
    punch = X.sine(lambda t: f_lo + 108.0 * p_mul * np.exp(-t * 32.0), n) * X.env_exp(n, 0.052, 0.001)
    body = X.band(rng.standard_normal(n), 120.0 * p_mul, 1850.0 * p_mul) * X.env_exp(n, 0.032, 0.0015)
    snap = X.band(rng.standard_normal(n), 900.0, 4600.0) * X.env_exp(n, 0.008, 0.0008) * 0.52
    bolt = X.band(rng.standard_normal(n), 1600.0, 3800.0) * X.env_exp(n, 0.016, 0.008) * 0.22
    tail = X.band(rng.standard_normal(n), 130.0, 1300.0) * X.env_exp(n, 0.095, 0.010) * 0.30
    return X.norm(punch * 1.30 + body * 1.15 + snap + bolt + tail)


def _shotgun_blast():
    n = int(0.75 * SR)
    boom = X.sine(lambda t: 46 + 115 * np.exp(-t * 22), n) * X.env_exp(n, 0.12, 0.002)
    blast = X.band(X.noise(n), 120, 4200) * X.env_exp(n, 0.065, 0.002)
    snap = X.band(X.noise(n), 1600, 9200) * X.env_exp(n, 0.014)
    tail = X.band(X.noise(n), 140, 1800) * X.env_exp(n, 0.26, 0.014) * 0.40
    return X.norm(boom * 1.35 + blast + snap * 0.8 + tail)


def _pump_rack():
    n = int(0.32 * SR)
    out = np.zeros(n)
    m1 = int(0.10 * SR)
    out[:m1] += X.band(X.noise(m1), 1600, 7200) * X.env_exp(m1, 0.014)
    off = int(0.13 * SR)
    m2 = n - off
    out[off:] += X.band(X.noise(m2), 1300, 7800) * X.env_exp(m2, 0.018) * 1.15
    return X.norm(out)


def _sniper_crack():
    """High-velocity rifle crack cutting through total winter silence into title slam."""
    n = int(1.15 * SR)
    whip = X.band(X.noise(n), 1600, 10500) * X.env_exp(n, 0.014, 0.001)
    punch = X.sine(lambda t: 52 + 165 * np.exp(-t * 32), n) * X.env_exp(n, 0.11, 0.001)
    echo = X.band(X.noise(n), 180, 2200) * X.env_exp(n, 0.42, 0.018) * 0.45
    return X.norm(whip * 1.15 + punch * 1.3 + echo)


def _impact_thwack(variant: int = 0):
    """Gritty dry marble/steel bullet impact thwack (replaces synthetic sine chirp!)."""
    rng = np.random.default_rng(810 + variant * 31)
    n = int(0.18 * SR)
    thud = X.band(rng.standard_normal(n), 180.0, 1100.0) * X.env_exp(n, 0.022, 0.001)
    grit = X.band(rng.standard_normal(n), 1200.0, 3600.0) * X.env_exp(n, 0.014, 0.001) * 0.65
    return X.norm(thud * 1.1 + grit)


def _fire_crackle(dur=4.6):
    """Warm rolling flame roar + soft timber crackles (no harsh high-freq static)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    roar = X.band(X.noise(n), 65, 420) * (0.68 + 0.32 * np.sin(2 * np.pi * 1.6 * t))
    hiss = X.band(X.noise(n), 380, 1650) * (0.60 + 0.40 * np.sin(2 * np.pi * 3.1 * t + 0.8)) * 0.42
    rng = np.random.default_rng(919)
    pops = np.zeros(n)
    k_pop = X.env_exp(int(0.014 * SR), 0.0028, 0.0008)
    for _ in range(int(dur * 12)):
        i = int(rng.integers(0, max(1, n - len(k_pop))))
        pops[i:i + len(k_pop)] += k_pop * rng.uniform(0.30, 0.85)
    pops = X.band(pops * rng.standard_normal(n), 850, 3600) * 0.85
    return X.fade(X.norm(roar * 1.2 + hiss + pops), 0.30, 0.35)


def _footsteps(n_steps=6, step_s=0.52, *, mode="solo", seed=701):
    """Distance-appropriate footsteps: 'snow' (muffled), 'solo' (heavy slow), 'patrol' (staggered squad)."""
    dur = n_steps * step_s + 0.45
    n = int(dur * SR)
    out = np.zeros(n)
    rng = np.random.default_rng(seed)
    layers = 3 if mode == "patrol" else 1
    for lyr in range(layers):
        off_t = lyr * 0.14 + float(rng.uniform(0.0, 0.05))
        sp = step_s * (1.0 + lyr * 0.04)
        for k in range(n_steps):
            i = int((off_t + k * sp + rng.uniform(-0.025, 0.025)) * SR)
            m = int(0.13 * SR)
            if i < 0 or i + m >= n:
                continue
            if mode == "snow":
                crunch = X.band(rng.standard_normal(m), 420, 2600) * X.env_exp(m, 0.038, 0.008)
                thud = X.band(rng.standard_normal(m), 55, 220) * X.env_exp(m, 0.030, 0.005) * 0.80
                step = crunch * 0.65 + thud
            else:
                heel = X.band(rng.standard_normal(m), 75, 580) * X.env_exp(m, 0.022, 0.003)
                grit = X.band(rng.standard_normal(m), 850, 3200) * X.env_exp(m, 0.016, 0.005) * 0.28
                step = heel + grit
            out[i:i + m] += step * rng.uniform(0.55, 0.95) * (0.72 if lyr > 0 else 1.0)
    return X.fade(X.norm(out), 0.08, 0.20)


def _police_siren(dur=3.4):
    """Distant low-passed two-tone patrol siren (consonant E-minor third, sits behind brass)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    doppler = 1.02 - 0.10 * (t / dur)
    # E5 / B4 consonant with the E-minor score, warmed & rolled off above 1250 Hz
    hi_lo = np.where((t % 0.74) < 0.37, 659.25, 493.88) * doppler
    tone = X.sine(lambda tt: hi_lo[np.minimum((tt * SR).astype(int), n - 1)], n)
    tone += 0.14 * X.sine(lambda tt: hi_lo[np.minimum((tt * SR).astype(int), n - 1)] * 2.0, n)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.75
    return X.fade(X.norm(X.band(tone, 320, 1250) * env), 0.22, 0.30)


def _spark_zap():
    n = int(0.26 * SR)
    buzz = X.sine(120.0, n) * 0.4 + X.band(X.noise(n), 2200, 10000)
    return X.norm(buzz * X.env_exp(n, 0.045, 0.001))


def _rocket_whoosh():
    n = int(1.45 * SR)
    t = np.arange(n) / SR
    env = np.clip(t / 0.14, 0, 1) * np.exp(-np.clip(t - 0.25, 0, None) / 0.55)
    hiss = X.band(X.noise(n), 450, 5600) * env
    roar = X.band(X.noise(n), 95, 650) * env * 0.95
    return X.norm(hiss + roar)


def _flare_pop():
    n = int(0.45 * SR)
    pop = X.sine(lambda t: 190 + 260 * np.exp(-t * 40), n) * X.env_exp(n, 0.03)
    sizzle = X.band(X.noise(n), 1800, 9500) * X.env_exp(n, 0.16, 0.008) * 0.55
    return X.norm(pop + sizzle)


def _bolt_click():
    n = int(0.24 * SR)
    a = X.band(X.noise(n), 1800, 7600) * X.env_exp(n, 0.009)
    b = np.zeros(n)
    off = int(0.085 * SR)
    b[off:] = (X.band(X.noise(n - off), 2200, 8800) * X.env_exp(n - off, 0.012))
    ring = X.sine(1680.0, n) * X.env_exp(n, 0.035) * 0.25
    return X.norm(a + b * 0.9 + ring)


def _reload_snap():
    n = int(0.32 * SR)
    c1 = X.band(X.noise(n), 1600, 6800) * X.env_exp(n, 0.014)
    off = int(0.11 * SR)
    c2 = np.zeros(n)
    c2[off:] = X.band(X.noise(n - off), 1200, 7400) * X.env_exp(n - off, 0.018)
    return X.norm(c1 + c2 * 1.1)


def _wind(dur, lo=160, hi=980):
    n = int(dur * SR)
    t = np.arange(n) / SR
    mod = 0.55 + 0.45 * np.sin(2 * np.pi * 0.32 * t) * np.sin(2 * np.pi * 0.14 * t + 0.7)
    return X.fade(X.norm(X.band(X.noise(n), lo, hi) * mod), 0.30, 0.30)


def _exhale():
    n = int(1.35 * SR)
    t = np.arange(n) / SR
    e = np.clip(t / 0.22, 0, 1) * np.exp(-np.clip(t - 0.22, 0, None) / 0.42)
    return X.norm(X.band(X.noise(n), 280, 2400) * e)


def _key_tick():
    n = int(0.015 * SR)
    return X.norm(X.band(X.noise(n), 2400, 9200) * X.env_exp(n, 0.0024))


def _engine_pass(dur=3.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.75
    growl = X.sine(lambda tt: 54 + 22 * np.sin(tt * 1.3), n) + 0.45 * X.sine(108.0, n)
    gravel = X.band(X.noise(n), 90, 950) * 0.55
    return X.fade(X.norm((growl * 0.65 + gravel) * env), 0.20, 0.25)


def _build_duck_envelope(n_tot: int, events: list) -> np.ndarray:
    """Dynamic music breath/sidechain envelope so explosions & gunfights punch cleanly."""
    env = np.ones(n_tot, dtype=np.float64)

    def dip(t0: float, t1: float, db: float):
        a = max(0, int(t0 * SR))
        b = min(n_tot, int(t1 * SR))
        if b > a:
            env[a:b] = np.minimum(env[a:b], 10.0 ** (db / 20.0))

    # Subtle musical breath dips right before the Act II and Act III drops
    dip(27.6, 28.78, -4.5)
    dip(56.4, 57.58, -4.5)
    # Give the dense rapid climax montage (64.8..76.8s) clean upper-mid headroom
    dip(64.8, 76.7, -1.8)
    # Give Act II/III gameplay & vehicle action breathing room beneath diegetic SFX
    for t_ev, kind in events:
        if kind == "explosion":
            dip(t_ev - 0.05, t_ev + 0.95, -5.8)
        elif kind in ("shotgun", "cookoff"):
            dip(t_ev - 0.03, t_ev + 0.45, -4.2)
        elif kind in ("lmg", "shot", "rocket"):
            dip(t_ev - 0.02, t_ev + 0.22, -2.8)
        elif kind in ("siren", "rotor_pass", "rotor_close"):
            dip(t_ev, t_ev + 1.4, -2.2)

    # Smooth 90 ms averaging window (zero zipper clicks)
    k = int(0.09 * SR)
    win = np.hanning(k)
    win /= win.sum()
    return np.convolve(env, win, mode="same")


def build_score(events_path: str | None = None, out_wav: str | None = None,
                music_path: str | None = None) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    out_wav = out_wav or os.path.join(OUT_DIR, "score.wav")
    rng = np.random.default_rng(2088)

    if music_path:
        music = _decode_external(music_path)
        n_tot = int(TOTAL * SR)
        if music.shape[1] < n_tot:
            music = np.pad(music, ((0, 0), (0, n_tot - music.shape[1])))
        else:
            music = music[:, :n_tot].copy()
        s0, s1 = int(SILENCE[0] * SR), int(SILENCE[1] * SR)
        ramp = int(0.05 * SR)
        music[:, s0 - ramp:s0] *= np.linspace(1.0, 0.0, ramp)
        music[:, s0:s1] = 0.0
    else:
        music = _build_procedural_music()

    ev_data = {"events": [], "typing_ticks": [], "cuts": []}
    if events_path and os.path.exists(events_path):
        with open(events_path, encoding="utf-8") as fh:
            ev_data = json.load(fh)

    n_tot = int(TOTAL * SR)
    duck = _build_duck_envelope(n_tot, ev_data.get("events", ()))
    # Music bed sits at 0.80 with live sidechain ducking so SFX breathes & punches!
    L = music[0].astype(np.float64) * 0.80 * duck
    R = music[1].astype(np.float64) * 0.80 * duck

    def add(t_s: float, sig: np.ndarray, gain_db: float = 0.0, pan: float = 0.0):
        i = int(round(t_s * SR))
        if i < 0 or i >= n_tot:
            return
        x = sig[:n_tot - i] * (10.0 ** (gain_db / 20.0))
        gl = np.cos((pan + 1.0) * np.pi / 4.0) * 1.414
        gr = np.sin((pan + 1.0) * np.pi / 4.0) * 1.414
        L[i:i + len(x)] += x * gl
        R[i:i + len(x)] += x * gr

    for t_hit in BIG_HITS:
        add(t_hit - 0.90, X.whoosh(0.90, up=True), -12.0)
        add(t_hit, X.boom(2.3 if t_hit == 80.4 else 1.5), -4.5 if t_hit == 80.4 else -7.5)

    for t_cut in ev_data.get("cuts", ()):
        if 64.5 <= t_cut <= 76.4:
            add(t_cut - 0.22, X.whoosh(0.22, up=True), -16.0, pan=float(rng.uniform(-0.45, 0.45)))

    for t_tick in ev_data.get("typing_ticks", ()):
        add(t_tick, _key_tick(), -20.0 + float(rng.uniform(-1.5, 1.5)), pan=-0.18)

    # Pitch/timbre-varied heavy, dry weapon & impact banks (zero repetitive synthetic beep!)
    shot_bank = [_rifle_shot(i) for i in range(4)]
    lmg_bank = [_lmg_shot(i) for i in range(4)]
    imp_bank = [_impact_thwack(i) for i in range(3)]
    sg_s = _shotgun_blast()
    pump_s = _pump_rack()
    exp_big = _explosion(big=True)
    exp_sm = _explosion(big=False)
    rk_s = _rocket_whoosh()
    fl_s = _flare_pop()
    rel_s = _reload_snap()
    bolt_s = _bolt_click()
    snip_s = _sniper_crack()
    zap_s = _spark_zap()
    steps_snow_s = _footsteps(6, 0.54, mode="snow", seed=701)
    steps_patrol_s = _footsteps(6, 0.46, mode="patrol", seed=703)
    steps_solo_s = _footsteps(6, 0.58, mode="solo", seed=705)

    for ev_i, (t_ev, kind) in enumerate(ev_data.get("events", ())):
        # Slightly pull back rapid montage gunshots so 01:11-01:16 stays wide & distortion-free
        climax_trim = -3.0 if 64.5 <= t_ev <= 76.7 else 0.0
        if kind == "shot":
            add(t_ev, shot_bank[ev_i % len(shot_bank)],
                -5.2 + climax_trim + float(rng.uniform(-1.0, 0.7)), pan=float(rng.uniform(-0.28, 0.28)))
        elif kind == "shotgun":
            add(t_ev, sg_s, -2.8 + climax_trim * 0.6, pan=-0.10)
        elif kind == "pump":
            add(t_ev, pump_s, -8.5 + climax_trim * 0.5, pan=-0.08)
        elif kind == "lmg":
            add(t_ev, lmg_bank[ev_i % len(lmg_bank)],
                -6.8 + climax_trim + float(rng.uniform(-0.9, 0.7)), pan=0.18)
        elif kind == "ricochet":
            add(t_ev, imp_bank[ev_i % len(imp_bank)],
                -10.5 + climax_trim + float(rng.uniform(-1.2, 0.8)), pan=float(rng.uniform(-0.45, 0.45)))
        elif kind == "explosion":
            add(t_ev, exp_big, -1.8, pan=0.0)
        elif kind == "cookoff":
            add(t_ev, exp_sm, -5.5, pan=0.14)
        elif kind == "rocket":
            add(t_ev, rk_s, -7.2 + climax_trim * 0.5, pan=0.22)
        elif kind == "flare":
            add(t_ev, fl_s, -10.0, pan=float(rng.uniform(-0.35, 0.35)))
        elif kind == "reload":
            add(t_ev, rel_s, -9.2, pan=-0.10)
        elif kind == "siren":
            add(t_ev, _police_siren(3.2), -16.5, pan=-0.34)
        elif kind == "spark_zap":
            add(t_ev, zap_s, -8.2 + climax_trim * 0.5, pan=-0.18)
        elif kind == "rotor_far":
            add(t_ev, X.rotor(4.6, 5.2, 6.2, low=64, interior=False), -13.5, pan=-0.15)
        elif kind == "rotor_in":
            add(t_ev, X.rotor(4.6, 6.4, 6.8, low=72, interior=True), -11.5, pan=0.0)
        elif kind == "rotor_close":
            add(t_ev, X.rotor(2.3, 6.8, 7.6, low=70, interior=False), -8.8, pan=0.25)
        elif kind == "rotor_pass":
            add(t_ev, X.rotor(2.3, 7.4, 5.2, low=66, interior=False), -8.2, pan=-0.35)
        elif kind == "engine_pass":
            add(t_ev, _engine_pass(3.6), -12.0, pan=-0.15)
        elif kind == "fire_crackle":
            add(t_ev, _fire_crackle(4.6), -15.5, pan=0.10)
        elif kind == "steps_snow":
            add(t_ev, steps_snow_s, -19.5, pan=-0.12)
        elif kind == "steps_patrol":
            add(t_ev, steps_patrol_s, -16.5, pan=0.08)
        elif kind == "steps_solo":
            add(t_ev, steps_solo_s, -17.5, pan=-0.06)
        elif kind == "wind_cold":
            add(t_ev, _wind(4.6, 140, 820), -18.5)
        elif kind == "wind_ridge":
            add(t_ev, _wind(3.55, 190, 1280), -17.0)
        elif kind == "exhale":
            add(t_ev, _exhale(), -16.5)
        elif kind == "bolt":
            add(t_ev, bolt_s, -9.0)
        elif kind == "sniper_shot":
            add(t_ev, snip_s, -1.5, pan=0.0)

    # Final stereo master (~ -14 LUFS / <= 0.90 peak)
    mix = np.stack([L, R], axis=1)
    tail = int(1.6 * SR)
    mix[-tail:] *= np.linspace(1.0, 0.0, tail)[:, None] ** 1.5
    ref = float(np.percentile(np.abs(mix), 99.92)) or 1.0
    mix = np.tanh(mix / ref * 1.06) * 0.88
    pcm = (np.clip(mix, -1.0, 1.0) * 32767.0).astype(np.int16)

    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
    print("score ->", out_wav)
    return out_wav


def main():
    ap = argparse.ArgumentParser(description="Build THE CALL 90s procedural trailer score.")
    ap.add_argument("--events", default=os.path.join(OUT_DIR, "events.json"))
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "score.wav"))
    ap.add_argument("--music", default=None, help="Optional external music track.")
    args = ap.parse_args()
    build_score(args.events, args.out, args.music)


if __name__ == "__main__":
    main()
