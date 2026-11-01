"""Mission 7 sound design: the farm day, the night raid, the ending receiver.

Mission-owned audio, same contract as ``missions.m6.m6_audio``: the generators
are registered with the shared AudioManager by ``M7Audio`` and every sound is
synthesised deterministically with numpy.  The repo ships no recorded M7 takes.

``M7Audio`` owns only the channels it starts.  It is silent-safe (no mixer, no
problem) and every loop is stopped on stage change, mission reset and quit.
"""
from functools import lru_cache
import io
import math
import wave

import numpy as np

RATE = 22050

LOOPS = (
    "m7_farm_bed",
    "m7_night_bed",
    "m7_choice_hum",
    "m7_gen_idle",
    "m7_trac_idle",
    "m7_trac_move",
)

FOLEY = (
    "m7_bird", "m7_hen", "m7_fence_creak", "m7_goat", "m7_bucket", "m7_crate",
    "m7_pig_squeal",
    "m7_dirt_step_1", "m7_dirt_step_2", "m7_dirt_step_3",
    "m7_well_crank", "m7_water_pour", "m7_grain_scoop", "m7_hay_rustle",
    "m7_gen_pull", "m7_gen_cough", "m7_gen_backfire", "m7_gen_catch",
    "m7_trac_rev", "m7_trac_stall", "m7_trac_off", "m7_chock",
    "m7_radio_tune", "m7_tx_lock",
)

WARM = LOOPS + FOLEY

# M6 foley M7 reuses (registered here so an M7 film cue can warm them).
_M6_REUSE = (
    "m6_paper", "m6_page_turn", "m6_rifle_rack", "m6_door_creak",
    "m6_truck_arrive", "m6_tailgate", "m6_headshot", "m6_report_far",
    "m6_rifle_crack", "m6_tink",
)


# ── tiny deterministic synth helpers ────────────────────────────────────────
def _t(n):
    return np.arange(n, dtype=np.float64) / RATE


def _noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def _lowpass(x, cutoff, poles=2):
    n = len(x)
    if n < 8:
        return x.copy()
    freqs = np.fft.rfftfreq(n, 1.0 / RATE)
    resp = 1.0 / np.sqrt(1.0 + (freqs / max(1.0, cutoff)) ** (2 * poles))
    return np.fft.irfft(np.fft.rfft(x) * resp, n)


def _highpass(x, cutoff):
    return x - _lowpass(x, cutoff, 1)


def _env(n, attack=0.02, release=0.2, peak=1.0):
    t = _t(n)
    dur = max(1e-3, n / RATE)
    a = np.clip(t / max(1e-4, attack), 0.0, 1.0)
    r = np.clip((dur - t) / max(1e-4, release), 0.0, 1.0)
    return peak * a * r


def _fade_edges(x, edge=0.02):
    n = len(x)
    k = max(1, int(edge * RATE))
    if n > 2 * k:
        x[:k] *= np.linspace(0.0, 1.0, k)
        x[-k:] *= np.linspace(1.0, 0.0, k)
    return x


def _stereo(x, width=0.12):
    d = int(0.011 * RATE)
    delayed = np.zeros_like(x)
    delayed[d:] = x[:-d]
    return np.column_stack((x, (1.0 - width) * x + width * delayed))


def _wav(pcm):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        frames = np.rint(np.clip(pcm, -0.92, 0.92) * 32767).astype("<i2")
        w.writeframes(frames.tobytes())
    return out.getvalue()


def _sweep(n, f0, f1):
    return np.cumsum(np.linspace(f0, f1, n)) / RATE


def _saw(freq_n, phase=0.0):
    return 2.0 * ((freq_n + phase) % 1.0) - 1.0


def _place(buf, seg, at, gain=1.0):
    i = int(at * RATE)
    if i >= len(buf):
        return
    k = min(len(seg), len(buf) - i)
    buf[i:i + k] += seg[:k] * gain


def _norm(x, peak=0.85):
    x = np.asarray(x, dtype=np.float64)
    pk = float(np.max(np.abs(x))) if len(x) else 0.0
    if pk > peak:
        x = x * (peak / pk)
    return x


def _done(x, stereo=0.12):
    x = _norm(x)
    x = _fade_edges(x, 0.006)
    pcm = _stereo(x, stereo)
    pcm[0] = 0.0
    pcm[-1] = 0.0
    pcm.setflags(write=False)
    return pcm


# ── loops ───────────────────────────────────────────────────────────────────
@lru_cache(maxsize=8)
def loop_pcm(name):
    if name == "m7_farm_bed":
        dur = 8.0
        n = int(RATE * dur)
        t = _t(n)
        wind = _lowpass(_noise(n, 701), 340.0, 2) * (
            0.50 + 0.22 * np.sin(2 * math.pi * t / dur * 1.5 + 0.3))
        leaves = _highpass(_lowpass(_noise(n, 702), 2600.0, 1), 900.0) * 0.055 * (
            0.5 + 0.5 * np.sin(2 * math.pi * t / dur * 4.0 + 1.1))
        x = wind + leaves
        for at, f0, f1 in ((0.9, 2500, 3300), (2.4, 2900, 3600), (5.7, 2300, 3100)):
            k = int(0.09 * RATE)
            chirp = np.sin(2 * math.pi * _sweep(k, f0, f1)) * _env(k, 0.008, 0.05) * 0.09
            _place(x, chirp, at)
            _place(x, chirp * 0.55, at + 0.14)
        k = int(0.55 * RATE)
        tt = _t(k)
        bleat = _lowpass(_saw(300.0 * tt + 3.0 * np.sin(2 * math.pi * 6.0 * tt)) * 0.05, 1300.0)
        bleat *= _env(k, 0.04, 0.18)
        _place(x, bleat, 6.5, 0.7)
        x *= _env(n, 0.9, 0.9)
        pcm = _stereo(x, 0.34)
    elif name == "m7_night_bed":
        dur = 8.0
        n = int(RATE * dur)
        t = _t(n)
        wind = _lowpass(_noise(n, 711), 250.0, 2) * (
            0.45 + 0.20 * np.sin(2 * math.pi * t / dur * 1.2 + 2.0))
        rumble = _lowpass(_noise(n, 712), 90.0, 3) * 0.25
        fires = np.zeros(n)
        rng = np.random.default_rng(713)
        for _ in range(34):
            at = float(rng.uniform(0.2, dur - 0.3))
            k = int(rng.uniform(0.015, 0.05) * RATE)
            pop = _highpass(_noise(k, int(rng.integers(1, 99999))), 1400.0)
            pop *= np.exp(-np.arange(k) / (0.008 * RATE)) * float(rng.uniform(0.06, 0.16))
            _place(fires, pop, at)
        x = (wind + rumble + fires) * _env(n, 0.9, 0.9)
        pcm = _stereo(x, 0.28)
    elif name == "m7_choice_hum":
        dur = 4.0
        n = int(RATE * dur)
        t = _t(n)
        hum = (np.sin(2 * math.pi * 50.0 * t) * 0.10
               + np.sin(2 * math.pi * 100.0 * t) * 0.045
               + np.sin(2 * math.pi * 150.0 * t) * 0.020)
        hiss = _highpass(_noise(n, 721), 2400.0) * 0.035
        carrier = np.sin(2 * math.pi * 1180.0 * t) * 0.012
        x = (hum + hiss + carrier) * _env(n, 0.5, 0.5)
        pcm = _stereo(x, 0.08)
    elif name == "m7_gen_idle":
        dur = 2.0
        n = int(RATE * dur)
        t = _t(n)
        pulse = (np.sin(2 * math.pi * 11.0 * t) > 0.0).astype(np.float64)
        pulse = _lowpass(pulse, 120.0, 1)
        thud = np.sin(2 * math.pi * 33.0 * t) * 0.30 + np.sin(2 * math.pi * 66.0 * t) * 0.10
        rattle = _highpass(_noise(n, 731), 800.0) * 0.05
        x = (thud * (0.55 + 0.45 * pulse) + rattle * (0.4 + 0.6 * pulse)
             + _lowpass(_noise(n, 732), 420.0, 2) * 0.30) * _env(n, 0.25, 0.25)
        pcm = _stereo(x, 0.10)
    elif name == "m7_trac_idle":
        dur = 2.0
        n = int(RATE * dur)
        t = _t(n)
        lope = 0.55 + 0.45 * np.sin(2 * math.pi * 9.0 * t)
        body = np.sin(2 * math.pi * 45.0 * t) * 0.30 + np.sin(2 * math.pi * 90.0 * t) * 0.12
        knock = _lowpass(_noise(n, 741), 320.0, 2) * 0.42
        x = (body * lope + knock) * _env(n, 0.3, 0.3)
        pcm = _stereo(x, 0.14)
    elif name == "m7_trac_move":
        dur = 1.2
        n = int(RATE * dur)
        t = _t(n)
        lope = 0.6 + 0.4 * np.sin(2 * math.pi * 9.0 * t)
        body = np.sin(2 * math.pi * 45.0 * t) * 0.24 + np.sin(2 * math.pi * 90.0 * t) * 0.10
        gravel = _highpass(_noise(n, 751), 1100.0) * 0.28 * (0.5 + 0.5 * np.sin(2 * math.pi * 7.0 * t))
        whine = np.sin(2 * math.pi * 610.0 * t) * 0.030
        x = (body * lope + gravel + whine) * _env(n, 0.18, 0.18)
        pcm = _stereo(x, 0.18)
    else:
        raise ValueError("Unknown M7 loop: " + name)
    peak = float(np.max(np.abs(pcm)))
    if peak > 0.85:
        pcm = pcm * (0.85 / peak)
    pcm[0] = 0.0
    pcm[-1] = 0.0
    pcm.setflags(write=False)
    return pcm


# ── one-shots ───────────────────────────────────────────────────────────────
@lru_cache(maxsize=64)
def foley_pcm(name):
    if name == "m7_bird":
        n = int(0.9 * RATE)
        x = np.zeros(n)
        for at, f0, f1 in ((0.0, 2600, 3400), (0.22, 3000, 2300)):
            k = int(0.10 * RATE)
            chirp = np.sin(2 * math.pi * _sweep(k, f0, f1)) * _env(k, 0.006, 0.05) * 0.5
            _place(x, chirp, at)
        flutter = _highpass(_noise(n, 801), 2200.0) * np.exp(-((_t(n) - 0.55) ** 2) / 0.006) * 0.18
        x += flutter
    elif name == "m7_hen":
        n = int(0.55 * RATE)
        x = np.zeros(n)
        for at, f, dur in ((0.0, 620.0, 0.10), (0.16, 520.0, 0.08), (0.30, 460.0, 0.12)):
            k = int(dur * RATE)
            kk = _t(k)
            cluck = _lowpass(_saw(f * kk) * 0.35, 1800.0) * _env(k, 0.004, 0.05)
            _place(x, cluck, at)
    elif name == "m7_fence_creak":
        n = int(0.9 * RATE)
        t = _t(n)
        f = 300 + 220 * np.sin(math.pi * np.clip(t / 0.6, 0.0, 1.0))
        creak = np.sign(np.sin(2 * math.pi * np.cumsum(f) / RATE)) * 0.14
        creak = _lowpass(creak, 1500.0) * np.exp(-((t - 0.32) ** 2) / 0.045)
        tick = _highpass(_noise(n, 811), 2400.0) * np.exp(-t * 90.0) * 0.30
        x = creak + tick
    elif name == "m7_goat":
        n = int(0.95 * RATE)
        t = _t(n)
        vib = 7.0 * np.sin(2 * math.pi * 6.0 * t)
        f = 285.0 + 30.0 * np.sin(math.pi * np.clip(t / 0.7, 0.0, 1.0)) + vib
        x = _lowpass(_saw(np.cumsum(f) / RATE) * 0.30, 1600.0)
        x *= _env(n, 0.03, 0.25)
        x += _highpass(_noise(n, 821), 1800.0) * np.exp(-((t - 0.05) ** 2) / 0.004) * 0.10
    elif name == "m7_pig_squeal":
        # One short, high, falling squeal: the farmyard's worst sound.
        n = int(0.85 * RATE)
        t = _t(n)
        wobble = 34.0 * np.sin(2 * math.pi * 23.0 * t)
        f = 880.0 * np.exp(-t * 1.9) + 240.0 + wobble
        x = _lowpass(_saw(np.cumsum(f) / RATE) * 0.30, 3200.0)
        x += np.sin(2 * math.pi * np.cumsum(f * 1.51) / RATE) * 0.12
        x *= _env(n, 0.008, 0.22)
        x += _highpass(_noise(n, 851), 1400.0) * np.exp(-t * 6.0) * 0.14
        x *= np.exp(-t * 0.7)
    elif name == "m7_bucket":
        n = int(0.45 * RATE)
        t = _t(n)
        x = (np.sin(2 * math.pi * 1180 * t) * 0.35 + np.sin(2 * math.pi * 2050 * t) * 0.20)
        x *= np.exp(-t * 26.0)
        x += _highpass(_noise(n, 831), 2000.0) * np.exp(-t * 60.0) * 0.25
    elif name == "m7_crate":
        n = int(0.5 * RATE)
        t = _t(n)
        thud = np.sin(2 * math.pi * 150 * t) * np.exp(-t * 20.0) * 0.5
        scuff = _lowpass(_noise(n, 841), 1400.0) * np.exp(-t * 9.0) * 0.45
        x = thud + scuff
    elif name.startswith("m7_dirt_step_"):
        seed = 851 + int(name[-1])
        n = int(0.24 * RATE)
        t = _t(n)
        crunch = _lowpass(_highpass(_noise(n, seed), 300.0), 1600.0) * np.exp(-t * 26.0) * 0.55
        thud = np.sin(2 * math.pi * 95 * t) * np.exp(-t * 30.0) * 0.28
        x = crunch + thud
    elif name == "m7_well_crank":
        n = int(1.8 * RATE)
        x = np.zeros(n)
        for i in range(7):
            k = int(0.035 * RATE)
            click = _highpass(_noise(k, 861 + i), 2200.0) * np.exp(-np.arange(k) / (0.006 * RATE))
            _place(x, click, 0.05 + i * 0.14, 0.32)
        rope = _lowpass(_noise(n, 869), 900.0) * _env(n, 0.1, 0.2) * 0.10
        tt = _t(n)
        splash = _highpass(_noise(n, 870), 700.0) * np.exp(-np.maximum(tt - 1.22, 0.0) * 9.0) \
            * (tt > 1.22) * 0.45
        x += rope + splash
    elif name == "m7_water_pour":
        n = int(1.4 * RATE)
        t = _t(n)
        stream = _highpass(_lowpass(_noise(n, 881), 2200.0, 1), 380.0) * 0.35
        stream *= 0.65 + 0.35 * np.sin(2 * math.pi * 4.0 * t + 0.5)
        x = stream * _env(n, 0.06, 0.25)
        for at in (0.35, 0.62, 0.95):
            k = int(0.05 * RATE)
            bubble = np.sin(2 * math.pi * _sweep(k, 700, 1400)) * _env(k, 0.004, 0.03) * 0.10
            _place(x, bubble, at)
    elif name == "m7_grain_scoop":
        n = int(0.8 * RATE)
        t = _t(n)
        swish = _highpass(_noise(n, 891), 900.0) * np.exp(-((t - 0.25) ** 2) / 0.03) * 0.35
        grain = np.zeros(n)
        rng = np.random.default_rng(892)
        for _ in range(26):
            at = float(rng.uniform(0.02, 0.6))
            k = int(0.012 * RATE)
            _place(grain, _highpass(_noise(k, int(rng.integers(1, 99999))), 2500.0)
                   * np.exp(-np.arange(k) / (0.004 * RATE)) * 0.16, at)
        x = swish + grain
    elif name == "m7_hay_rustle":
        n = int(0.75 * RATE)
        t = _t(n)
        x = _highpass(_noise(n, 901), 1600.0)
        x *= (np.exp(-((t - 0.12) ** 2) / 0.01) + 0.7 * np.exp(-((t - 0.34) ** 2) / 0.02)
              + 0.4 * np.exp(-((t - 0.55) ** 2) / 0.015)) * 0.40
    elif name == "m7_gen_pull":
        n = int(0.5 * RATE)
        t = _t(n)
        zip_ = _highpass(_noise(n, 911), 900.0) * np.exp(-((t - 0.10) ** 2) / 0.0025) * 0.55
        clack = (np.sin(2 * math.pi * 210 * t) + 0.6 * np.sin(2 * math.pi * 430 * t))
        clack *= np.exp(-np.maximum(t - 0.26, 0.0) * 40.0) * (t > 0.26) * 0.55
        x = zip_ + clack
    elif name == "m7_gen_cough":
        n = int(0.75 * RATE)
        t = _t(n)
        chug = np.sin(2 * math.pi * 38 * t) * (0.5 + 0.5 * np.sin(2 * math.pi * 9 * t)) * 0.45
        chug *= np.exp(-t * 4.5)
        chuff = _lowpass(_noise(n, 921), 600.0) * np.exp(-t * 3.0) * 0.35
        x = chug + chuff
    elif name == "m7_gen_backfire":
        n = int(0.55 * RATE)
        t = _t(n)
        x = _lowpass(_noise(n, 931), 2600.0) * np.exp(-t * 26.0) * 0.9
        x += np.sin(2 * math.pi * 55 * t) * np.exp(-t * 10.0) * 0.45
    elif name == "m7_gen_catch":
        n = int(1.5 * RATE)
        t = _t(n)
        f = 30 + 12 * np.clip(t / 0.9, 0.0, 1.0)
        chug = np.sin(2 * math.pi * np.cumsum(f) / RATE) * 0.45
        chug *= (0.55 + 0.45 * np.sin(2 * math.pi * (8 + 6 * np.clip(t / 1.2, 0.0, 1.0)) * t))
        chug *= np.clip(t / 0.12, 0.0, 1.0)
        chug += _lowpass(_noise(n, 941), 500.0) * 0.28 * np.clip(t / 0.4, 0.0, 1.0)
        x = chug * np.exp(-np.maximum(t - 1.05, 0.0) * 2.2)
    elif name == "m7_trac_rev":
        n = int(0.95 * RATE)
        t = _t(n)
        f = 42.0 + 46.0 * np.clip(t / 0.55, 0.0, 1.0) - 18.0 * np.clip((t - 0.6) / 0.35, 0.0, 1.0)
        ph = np.cumsum(f) / RATE
        x = (np.sin(2 * math.pi * ph) * 0.32 + np.sin(4 * math.pi * ph) * 0.12)
        x *= 0.7 + 0.3 * np.sin(2 * math.pi * 9.0 * t)
        x += _lowpass(_noise(n, 951), 700.0) * 0.22 * np.clip(t / 0.2, 0.0, 1.0)
        x *= _env(n, 0.03, 0.25)
    elif name == "m7_trac_stall":
        n = int(1.0 * RATE)
        t = _t(n)
        f = 46.0 - 30.0 * np.clip(t / 0.8, 0.0, 1.0)
        ph = np.cumsum(f) / RATE
        x = np.sin(2 * math.pi * ph) * 0.30 * (0.5 + 0.5 * np.sin(2 * math.pi * 6.0 * t))
        sput = _lowpass(_noise(n, 961), 420.0) * np.exp(-t * 2.4) * 0.45
        x = (x + sput) * np.exp(-np.maximum(t - 0.6, 0.0) * 9.0)
    elif name == "m7_trac_off":
        n = int(1.3 * RATE)
        t = _t(n)
        f = 40.0 - 34.0 * np.clip(t / 1.0, 0.0, 1.0)
        x = np.sin(2 * math.pi * np.cumsum(f) / RATE) * 0.28 * np.exp(-t * 1.6)
        x += np.sin(2 * math.pi * 70 * t) * np.exp(-np.maximum(t - 0.95, 0.0) * 24.0) * (t > 0.95) * 0.35
    elif name == "m7_chock":
        n = int(0.4 * RATE)
        t = _t(n)
        x = (np.sin(2 * math.pi * 190 * t) * 0.45 + np.sin(2 * math.pi * 410 * t) * 0.18)
        x *= np.exp(-t * 23.0)
        x += _lowpass(_noise(n, 971), 1200.0) * np.exp(-t * 40.0) * 0.3
    elif name == "m7_radio_tune":
        n = int(0.2 * RATE)
        t = _t(n)
        click = _highpass(_noise(n, 981), 2200.0) * np.exp(-t * 120.0) * 0.55
        tick = _highpass(_noise(n, 982), 1400.0) * np.exp(-np.maximum(t - 0.07, 0.0) * 60.0) \
            * (t > 0.07) * 0.3
        x = click + tick
    elif name == "m7_tx_lock":
        n = int(0.5 * RATE)
        t = _t(n)
        clunk = (np.sin(2 * math.pi * 95 * t) + 0.5 * np.sin(2 * math.pi * 210 * t))
        clunk *= np.exp(-np.maximum(t - 0.05, 0.0) * 18.0) * (t > 0.05) * 0.55
        relay = _highpass(_noise(n, 991), 1800.0) * np.exp(-np.maximum(t - 0.06, 0.0) * 26.0) \
            * (t > 0.06) * 0.35
        x = clunk + relay
    else:
        raise ValueError("Unknown M7 foley: " + name)
    return _done(x)


GENERATORS = [(name, lambda name=name: _wav(loop_pcm(name))) for name in LOOPS]
GENERATORS += [(name, lambda name=name: _wav(foley_pcm(name))) for name in FOLEY]


# ── manager ─────────────────────────────────────────────────────────────────
class M7Audio:
    """Own only the channels this mission starts; silent-safe everywhere."""

    def __init__(self, manager):
        self.manager = manager
        self.loops = {}
        self.gains = {}
        self.one_shots = []
        self.paused = False
        self.closed = False
        try:
            manager.register_lazy_generators(GENERATORS)
            from missions.m6.m6_audio import GENERATORS as _m6
            manager.register_lazy_generators(_m6)
        except Exception:
            pass

    def warm(self):
        """Synthesise every sound this mission can play (mission load only)."""
        for name in WARM + _M6_REUSE + ("shotgun_blast", "shotgun_pump", "shell_insert"):
            try:
                self.manager.get_sound(name)
            except Exception:
                pass

    def start_loop(self, name, gain=0.2):
        if self.closed:
            return
        self.stop_loop(name)
        sound = self.manager.get_sound(name)
        if sound is None:
            return
        try:
            ch = sound.play(loops=-1)
        except Exception:
            ch = None
        if ch is None:
            return
        self.loops[name] = ch
        self.gains[name] = float(gain)
        self._apply(name)

    def _apply(self, name):
        ch = self.loops.get(name)
        if ch is None:
            return
        master = float(getattr(self.manager, "master_volume", 0.8))
        sfx = float(getattr(self.manager, "sfx_volume", 1.0))
        try:
            ch.set_volume(max(0.0, min(1.0, master * sfx * self.gains.get(name, 0.2))))
        except Exception:
            pass

    def refresh(self):
        for name in list(self.loops):
            self._apply(name)

    def stop_loop(self, name):
        ch = self.loops.pop(name, None)
        self.gains.pop(name, None)
        if ch is not None:
            try:
                ch.stop()
            except Exception:
                pass

    def stop_loops(self):
        for name in list(self.loops):
            self.stop_loop(name)

    def _one(self, name, volume):
        if self.closed:
            return
        try:
            ch = self.manager.play(name, volume=volume)
        except Exception:
            return
        if ch is not None:
            self.one_shots.append((ch, ch.get_sound()))
        if len(self.one_shots) > 24:
            self.one_shots = [(c, s) for c, s in self.one_shots
                              if c.get_busy() and c.get_sound() is s]

    def pause(self):
        if self.paused or self.closed:
            return
        self.paused = True
        for ch in list(self.loops.values()):
            try:
                ch.pause()
            except Exception:
                pass
        try:
            self.manager.pause_music()
        except Exception:
            pass

    def resume(self):
        if not self.paused or self.closed:
            return
        self.paused = False
        for ch in list(self.loops.values()):
            try:
                ch.unpause()
            except Exception:
                pass
        try:
            self.manager.unpause_music()
        except Exception:
            pass
        self.refresh()

    def stop(self):
        if self.closed:
            return
        self.closed = True
        self.stop_loops()
        for ch, _s in self.one_shots:
            try:
                ch.stop()
            except Exception:
                pass
        self.one_shots.clear()

    # farm ---------------------------------------------------------------
    def step(self, i):
        self._one("m7_dirt_step_%d" % (int(i) % 3 + 1), 0.16)

    def dialogue_tick(self):
        self._one("type_tick", 0.05)

    def bird(self):
        self._one("m7_bird", 0.22)

    def hen(self):
        self._one("m7_hen", 0.20)

    def pig_squeal(self):
        self._one("m7_pig_squeal", 0.55)

    def goat(self):
        self._one("m7_goat", 0.22)

    def fence_creak(self):
        self._one("m7_fence_creak", 0.30)

    def bucket(self):
        self._one("m7_bucket", 0.30)

    def crate(self):
        self._one("m7_crate", 0.30)

    def well(self):
        self._one("m7_well_crank", 0.45)

    def pour(self):
        self._one("m7_water_pour", 0.45)

    def grain(self):
        self._one("m7_grain_scoop", 0.40)

    def hay(self):
        self._one("m7_hay_rustle", 0.40)

    def door(self):
        self._one("door_creak", 0.35)

    # generator ----------------------------------------------------------
    def gen_pull(self):
        self._one("m7_gen_pull", 0.50)

    def gen_cough(self):
        self._one("m7_gen_cough", 0.45)

    def gen_backfire(self):
        self._one("m7_gen_backfire", 0.55)

    def gen_catch(self):
        self._one("m7_gen_catch", 0.55)

    # tractor ------------------------------------------------------------
    def trac_idle(self):
        self.start_loop("m7_trac_idle", 0.20)

    def trac_move(self):
        self.start_loop("m7_trac_move", 0.22)

    def trac_still(self):
        self.stop_loop("m7_trac_move")

    def trac_rev(self):
        self._one("m7_trac_rev", 0.45)

    def trac_stall(self):
        self._one("m7_trac_stall", 0.50)

    def trac_off(self):
        self.stop_loops()
        self._one("m7_trac_off", 0.45)

    def chock(self):
        self._one("m7_chock", 0.40)

    # radio / receiver ---------------------------------------------------
    def power_on(self):
        self._one("crt_thunk", 0.40)
        self._one("crt_whine", 0.16)

    def click(self):
        self._one("menu_click", 0.30)

    def radio_tune(self):
        self._one("m7_radio_tune", 0.35)

    def tx_lock(self):
        self._one("m7_tx_lock", 0.45)

    # raid (the method names the raid already calls) ---------------------
    def shot(self, _suppressed=True):
        self._one("shotgun_blast", 0.62)

    def pump(self):
        self._one("shotgun_pump", 0.45)

    def shell_in(self):
        self._one("shell_insert", 0.40)

    def guard_shot(self):
        self._one("m6_rifle_crack", 0.42)

    def impact(self, on_enemy=False):
        self._one("bullet_impact_enemy" if on_enemy else "bullet_impact",
                  0.5 if on_enemy else 0.32)

    def dry(self):
        self._one("empty_click", 0.5)

    def reload(self):
        self._one("reload", 0.45)

    def headshot(self):
        self._one("m6_headshot", 0.5)

    def report(self):
        self._one("m6_report_far", 0.7)

    def truck_arrive(self):
        self._one("m6_truck_arrive", 0.55)

    def tailgate(self):
        self._one("m6_tailgate", 0.5)


# ── score (assets/music/ost, streamed) ──────────────────────────────────────
# cue -> (file, volume, fade-in ms). Volume is the play_music() scale (the menu
# theme sits at 0.48), so the farm cue stays under the yard foley and Bodi.
OST_DIR = "assets/music/ost/"
MUSIC = {
    "farm": (OST_DIR + "05_curfew_dawn.mp3", 0.30, 2500),
    "raid": (OST_DIR + "06_not_tonight.mp3", 0.42, 1500),
    "film": (OST_DIR + "03_quiet_on_route_12.mp3", 0.36, 2000),
    "outro": (OST_DIR + "08_i_chose_the_many.mp3", 0.48, 2500),
}
MUSIC_FILES = frozenset(spec[0] for spec in MUSIC.values())
MUSIC_FADE_OUT_MS = 1500
_MUSIC_FAILED = set()


def music(manager, cue):
    """Drive the streamed score toward ``cue`` (None = silence); call every frame.

    Same cue: keeps the track running (no restart). New cue: fades the old
    track out first, then fades the new one in once the fade-out has ended.
    """
    spec = MUSIC.get(cue)
    want = spec[0] if spec else None
    try:
        current = manager.music_name()
        if want is not None and want == current:
            manager.play_music(want, volume=spec[1], fade_ms=spec[2])
            return
        if current is not None:
            manager.fade_out_music(MUSIC_FADE_OUT_MS)
            return
        if want is None or want in _MUSIC_FAILED or manager.music_busy():
            return
        if not manager.play_music(want, volume=spec[1], fade_ms=spec[2]):
            _MUSIC_FAILED.add(want)     # missing/undecodable: don't retry every frame
    except Exception:
        pass


AUDIO = None


def instance(manager):
    """The mission singleton; a stopped one is replaced on next use."""
    global AUDIO
    if AUDIO is None or AUDIO.closed:
        AUDIO = M7Audio(manager)
    return AUDIO
