"""egg666_audio.py - procedural sound for the 3D "666" scare.

Everything is synthesised with numpy, deterministically, and registered lazily
with the shared AudioManager by ``begin()``: nothing is built at import time
and the repo ships no recorded take.  The scare's rule is silence, so this
module plays nothing by itself: ``egg666_3d`` calls ``one_shot`` / ``bed`` /
``beat`` only where its timeline marks a sound, and ``stop`` cuts them all.
Pan (-1 left .. 1 right) and level carry the demon's position.
"""
import io
import wave

import numpy as np

RATE = 22050

NAMES = ("egg666_buzz", "egg666_drone", "egg666_heart", "egg666_breath",
         "egg666_crack", "egg666_groan", "egg666_sting", "egg666_thud")

_beds = {}                  # looping sound name -> its channel
_beat = {"next": 0}         # frame of the next heartbeat


# -- tiny deterministic synth helpers ----------------------------------------
def _t(n):
    return np.arange(n, dtype=np.float64) / RATE


def _noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def _shape(x, resp):
    n = len(x)
    f = np.fft.rfftfreq(n, 1.0 / RATE)
    return np.fft.irfft(np.fft.rfft(x) * resp(f), n)


def _lowpass(x, fc, poles=2):
    return _shape(x, lambda f: 1.0 / np.sqrt(1.0 + (f / fc) ** (2 * poles)))


def _highpass(x, fc, poles=2):
    return _shape(x, lambda f: (f / fc) ** poles / np.sqrt(1.0 + (f / fc) ** (2 * poles)))


def _band(x, fc, bw):
    return _shape(x, lambda f: np.exp(-0.5 * ((f - fc) / bw) ** 2))


def _norm(x, peak):
    m = float(np.max(np.abs(x))) or 1.0
    return x * (peak / m)


def _fade(x, edge=0.008):
    k = max(1, int(edge * RATE))
    if len(x) > 2 * k:
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
        w.writeframes(np.rint(np.clip(pcm, -0.92, 0.92) * 32767).astype("<i2").tobytes())
    return out.getvalue()


def _phase(freq):
    return 2.0 * np.pi * np.cumsum(freq) / RATE


# -- the eight sounds --------------------------------------------------------
def _buzz():
    """A failing bulb: a dry click, then mains hum that stutters and dies."""
    n = int(0.30 * RATE)
    t = _t(n)
    hum = (np.sin(2 * np.pi * 100 * t) + 0.5 * np.sin(2 * np.pi * 200 * t)
           + 0.3 * np.sin(2 * np.pi * 300 * t))
    gate = (np.sin(2 * np.pi * 23 * t) > -0.2).astype(np.float64)
    env = np.clip(t / 0.004, 0.0, 1.0) * np.exp(-t * 6.0)
    spit = _highpass(_noise(n, 12), 2500) * (np.abs(_noise(n, 14)) > 2.3) * 3.0
    click = _highpass(_noise(n, 13), 1800) * np.exp(-t * 420.0)
    x = 0.55 * hum * gate * env + 0.5 * spit * env + 0.9 * click
    return _wav(_stereo(_fade(_norm(x, 0.7), 0.0015), 0.08))


def _drone():
    """Four seconds of sub-bass that loops without a seam (whole cycles only)."""
    n = 4 * RATE
    t = _t(n)
    tone = (0.55 * np.sin(2 * np.pi * 40 * t) + 0.45 * np.sin(2 * np.pi * 55 * t)
            + 0.40 * np.sin(2 * np.pi * 55.5 * t) + 0.18 * np.sin(2 * np.pi * 82 * t + 1.0)
            + 0.14 * np.sin(2 * np.pi * 110 * t + 0.4) + 0.08 * np.sin(2 * np.pi * 165 * t + 0.5))
    tone *= 0.75 + 0.25 * np.sin(2 * np.pi * 0.25 * t)
    rumble = _norm(_lowpass(_noise(n, 21), 120, 3), 0.45)
    return _wav(_stereo(_norm(tone, 0.55) + rumble * 0.6, 0.2))


def _heart():
    """One distorted 'lub-dub'; the caller repeats it faster and faster."""
    n = int(0.62 * RATE)
    t = _t(n)

    def thump(t0, amp, f0, f1):
        tt = np.clip(t - t0, 0.0, None)
        env = (t >= t0) * np.exp(-tt * 38.0) * np.clip(tt / 0.003, 0.0, 1.0)
        return amp * env * np.sin(_phase(f1 + (f0 - f1) * np.exp(-tt * 30.0)))

    x = thump(0.0, 1.0, 95, 42) + thump(0.21, 0.72, 85, 38)
    x += 0.25 * _lowpass(_noise(n, 31), 400) * np.exp(-t * 50.0)
    return _wav(_stereo(_norm(np.tanh(2.6 * x), 0.9), 0.05))


def _breath():
    """Close, wet breathing: a 3.2 s inhale/exhale cycle that loops."""
    dur = 3.2
    n = int(dur * RATE)
    ph = _t(n) / dur

    def bump(c, w):
        return np.exp(-0.5 * ((ph - c) / w) ** 2)

    base = _noise(n, 41)
    inhale = _band(base, 1500, 700) * bump(0.24, 0.085)
    exhale = (_band(base, 900, 500) + 0.5 * _band(_noise(n, 42), 2500, 900)) * bump(0.72, 0.11)
    low = _lowpass(base, 260) * bump(0.72, 0.11) * 1.2
    x = 0.7 * inhale + 0.9 * exhale + low
    return _wav(_stereo(_fade(_norm(x, 0.8), 0.01), 0.14))


def _crack():
    """Joints going the wrong way: six dry pops, a wet thock and a creak."""
    n = RATE
    t = _t(n)
    rng = np.random.default_rng(51)
    x = np.zeros(n)
    for t0, amp, fc in ((0.000, 1.00, 1900), (0.034, 0.70, 1200), (0.092, 0.90, 2400),
                        (0.118, 0.55, 800), (0.236, 0.80, 1500), (0.412, 0.65, 2100)):
        i0 = int(t0 * RATE)
        tt = t[:n - i0]
        ring = np.sin(2 * np.pi * fc * tt) * np.exp(-tt * (500.0 + 0.15 * fc))
        burst = _highpass(rng.standard_normal(n - i0), 900) * np.exp(-tt * 700.0)
        x[i0:] += amp * (0.7 * ring + 0.5 * burst)
    thock = np.sin(_phase(70 + 90 * np.exp(-t * 60.0))) * np.exp(-t * 30.0) * 0.8
    cf = 170 + 330 * np.clip(t / 0.55, 0.0, 1.0) ** 1.5 + 14 * np.sin(2 * np.pi * 23 * t)
    creak = np.where(np.sin(_phase(cf)) > 0, 1.0, -1.0)
    creak = _lowpass(creak, 1400) * np.clip(t / 0.05, 0.0, 1.0) * np.clip((0.6 - t) / 0.2, 0.0, 1.0) * 0.18
    return _wav(_stereo(_fade(_norm(x + thock + creak, 0.9), 0.001), 0.1))


def _groan():
    """The jaw opening: a slow throat growl sinking in pitch."""
    dur = 1.9
    n = int(dur * RATE)
    t = _t(n)
    f = 80.0 - 28.0 * (t / dur) ** 0.7 + 2.5 * np.sin(2 * np.pi * 5.5 * t)
    saw = _lowpass(2.0 * ((np.cumsum(f) / RATE) % 1.0) - 1.0, 520)
    growl = _lowpass(_noise(n, 61), 300) * (0.5 + 0.5 * np.sin(2 * np.pi * 14 * t))
    env = np.clip(t / 0.35, 0.0, 1.0) * np.clip((dur - t) / 0.6, 0.0, 1.0)
    return _wav(_stereo(_norm((saw * 0.8 + growl * 0.9) * env, 0.8), 0.12))


def _sting():
    """The scream: a pitch that jumps up, wavers and sags, torn by distortion,
    under a sub boom.  Hard onset, no fade-in."""
    dur = 2.0
    n = int(dur * RATE)
    t = _t(n)
    base = np.interp(t, [0.0, 0.10, 0.45, 1.2, 2.0], [760, 1650, 1320, 900, 520])
    vib = 1.0 + 0.07 * np.sin(2 * np.pi * 11 * t) + 0.04 * np.sin(2 * np.pi * 23.3 * t)
    jit = 1.0 + 0.05 * _norm(_lowpass(_noise(n, 71), 30), 1.0)
    ph = _phase(base * vib * jit)
    src = np.zeros(n)
    for k in range(1, 15):
        src += np.sin(k * ph + 0.3 * k) / k ** 0.9
    voiced = _band(src, 900, 350) + 0.8 * _band(src, 2300, 600) + 0.25 * src
    rasp = _highpass(_noise(n, 72), 1800) * (0.5 + 0.5 * np.sin(2 * np.pi * 60 * t)) * 0.9
    env = np.clip(t / 0.004, 0.0, 1.0) * np.where(t < 1.1, 1.0, np.exp(-(t - 1.1) * 4.0))
    scream = np.tanh(3.2 * _norm(voiced + 0.6 * rasp, 1.0)) * env
    boom = np.sin(_phase(30 + 90 * np.exp(-t * 7.0))) * np.exp(-t * 4.2)
    hiss = 0.25 * _highpass(_noise(n, 73), 3500) * np.exp(-t * 12.0)
    return _wav(_stereo(_norm(0.9 * scream + 0.9 * boom + hiss, 0.92), 0.2))


def _thud():
    """A heavy step or a slam, felt more than heard."""
    n = int(0.45 * RATE)
    t = _t(n)
    x = np.sin(_phase(36 + 40 * np.exp(-t * 28.0))) * np.exp(-t * 11.0)
    x += 0.6 * _lowpass(_noise(n, 81), 380) * np.exp(-t * 24.0)
    x += 0.15 * _highpass(_noise(n, 82), 1500) * np.exp(-t * 160.0)
    return _wav(_stereo(_fade(_norm(x, 0.9), 0.002), 0.06))


_GEN = {
    "egg666_buzz": _buzz, "egg666_drone": _drone, "egg666_heart": _heart,
    "egg666_breath": _breath, "egg666_crack": _crack, "egg666_groan": _groan,
    "egg666_sting": _sting, "egg666_thud": _thud,
}


# -- playback ----------------------------------------------------------------
def _mgr():
    from core.config import audio as manager  # lazy: the shared AudioManager
    return manager


def _lr(pan):
    pan = max(-1.0, min(1.0, pan))
    return min(1.0, 1.0 - pan), min(1.0, 1.0 + pan)


def hush():
    """Silence the world: the scare starts from dead quiet."""
    _mgr().hard_stop(music=True)


def begin():
    """Register and pre-build every sound (call it behind the black cut)."""
    _beds.clear()
    _beat["next"] = 0
    m = _mgr()
    m.register_lazy_generators([(name, _GEN[name]) for name in NAMES])
    for name in NAMES:
        m.get_sound(name)
    return all(m.sounds.get(name) is not None for name in NAMES)


def one_shot(name, volume=1.0, pan=0.0):
    ch = _mgr().play(name, volume=volume)
    if ch:
        ch.set_volume(*_lr(pan))
    return ch


def bed(name, level, pan=0.0):
    """Keep a looping sound running at ``level`` (0 stops it)."""
    ch = _beds.get(name)
    if level <= 0.002:
        if ch is not None:
            ch.stop()
            _beds.pop(name, None)
        return
    if ch is None or not ch.get_busy():
        ch = _beds[name] = _mgr().play(name, volume=1.0, loops=-1)
    if ch:
        left, right = _lr(pan)
        ch.set_volume(level * left, level * right)


def beat(f, period, level, pan=0.0):
    """One heartbeat whenever frame ``f`` reaches the next due frame; the
    caller shortens ``period`` (frames) to make it race."""
    if f >= _beat["next"]:
        one_shot("egg666_heart", level, pan)
        _beat["next"] = f + max(8, int(period))


def stop():
    try:
        m = _mgr()
        for name in NAMES:
            m.stop(name)
    except Exception:
        pass
    _beds.clear()
