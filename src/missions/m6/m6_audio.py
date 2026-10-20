"""Mission 6 sound design: film stems, foley and the interactive-train bed.

Mission-owned audio (same contract as ``missions.m5.finale_audio``): this
module registers its lazy generators with the shared AudioManager when
``M6FilmAudio`` is created, and never imports the shared audio package at
module scope.  Every sound is synthesised deterministically with numpy; the
repo ships no recorded M6 takes.

``M6FilmAudio`` owns only its own channels.  It reads the current film shot
from ``core.cutscene_registry`` so scene changes drive the stem, and it is
compatible with the app's CutscenePlayer hooks
(``prepare/track/update/pause/resume/stop``).
"""
from functools import lru_cache
import io
import math
import wave

import numpy as np

RATE = 22050

STEMS = ("m6_wind_bed", "m6_heli_bed", "m6_train_idle", "m6_room_tone")
FOLEY = (
    "m6_rotor_away", "m6_jump", "m6_wind_gust", "m6_fall", "m6_land",
    "m6_heli_away", "m6_boxcar_door", "m6_breath", "m6_paper",
    "m6_page_turn", "m6_snow_step", "m6_notebook_close", "m6_terminal_beep",
    "m6_radio_static", "m6_rifle_crack", "m6_train_depart", "m6_doors_close",
    "m6_tinnitus", "m6_report_far", "m6_body_thud",
    "m6_whiz", "m6_headshot", "m6_tink",
)

# Scene -> looping stems.  Every film scene is listed; unlisted scenes (the
# title card) stay silent.
SCENE_STEMS = {
    "m6_insert_heli": ("m6_heli_bed", "m6_wind_bed"),
    "m6_insert_jump": ("m6_heli_bed", "m6_wind_bed"),
    "m6_insert_fall": ("m6_wind_bed",),
    "m6_insert_ground": ("m6_wind_bed",),
    "m6_boxcar_wide": ("m6_room_tone",),
    "m6_boxcar_notebook": ("m6_room_tone",),
    "m6_boxcar_volkov": ("m6_room_tone",),
    "m6_boxcar_biribel": ("m6_room_tone",),
    "m6_boxcar_exit": ("m6_room_tone",),
    "m6_customs_terminal": ("m6_room_tone",),
    "m6_radio_vasile": ("m6_room_tone",),
    "m6_radio_maru": ("m6_room_tone",),
    "m6_helicopter": ("m6_wind_bed", "m6_heli_bed"),
}

_STEM_GAIN = {
    "m6_wind_bed": 0.55, "m6_heli_bed": 0.52,
    "m6_train_idle": 0.50, "m6_room_tone": 0.32,
}
_FOLEY_GAIN = {
    "m6_rotor_away": 0.7, "m6_jump": 0.65, "m6_wind_gust": 0.5,
    "m6_fall": 0.55, "m6_land": 0.8, "m6_heli_away": 0.7,
    "m6_boxcar_door": 0.7, "m6_breath": 0.4, "m6_paper": 0.55,
    "m6_page_turn": 0.5, "m6_snow_step": 0.5, "m6_notebook_close": 0.6,
    "m6_terminal_beep": 0.5, "m6_radio_static": 0.55,
    "m6_rifle_crack": 0.85, "m6_train_depart": 0.75, "m6_doors_close": 0.7,
    "m6_tinnitus": 0.32, "m6_report_far": 0.7, "m6_body_thud": 0.8,
    "m6_whiz": 0.5, "m6_headshot": 0.6, "m6_tink": 0.35,
}


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


def _stereo(x, width=0.12, seed=1):
    d = int(0.011 * RATE)
    delayed = np.zeros_like(x)
    delayed[d:] = x[:-d]
    r = (1.0 - width) * x + width * delayed
    return np.column_stack((x, r))


def _mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def _wav(pcm):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        frames = np.rint(np.clip(pcm, -0.92, 0.92) * 32767).astype("<i2")
        w.writeframes(frames.tobytes())
    return out.getvalue()


# ── stems ───────────────────────────────────────────────────────────────────
@lru_cache(maxsize=8)
def stem_pcm(name):
    if name == "m6_wind_bed":
        dur = 6.0
        n = int(RATE * dur)
        t = _t(n)
        base = _lowpass(_noise(n, 11), 420.0, 2) * 0.55
        gust = 0.6 + 0.4 * np.sin(2 * math.pi * t / dur * 2 + 0.4)
        whistle = _highpass(_noise(n, 12), 900.0) * 0.05 * \
            (0.5 + 0.5 * np.sin(2 * math.pi * t / dur * 3 + 1.2))
        x = (base * gust + whistle) * _env(n, 0.8, 1.1)
        pcm = _stereo(x, 0.30, 11)
    elif name == "m6_heli_bed":
        dur = 3.0
        n = int(RATE * dur)
        t = _t(n)
        chop = 0.55 + 0.45 * np.sign(np.sin(2 * math.pi * 13.0 * t))
        body = _lowpass(_noise(n, 21), 300.0, 2) * chop * 0.8
        turbine = (np.sin(2 * math.pi * 118 * t) * 0.05
                   + np.sin(2 * math.pi * 236 * t) * 0.025)
        x = (body + turbine) * _env(n, 0.35, 0.55)
        pcm = _stereo(x, 0.22, 21)
    elif name == "m6_train_idle":
        dur = 4.0
        n = int(RATE * dur)
        t = _t(n)
        rumble = _lowpass(_noise(n, 31), 150.0, 3) * 1.4
        diesel = np.sin(2 * math.pi * 42.0 * t) * 0.10 * \
            (0.7 + 0.3 * np.sin(2 * math.pi * 0.7 * t))
        clank = np.zeros(n)
        rng = np.random.default_rng(31)
        for ms in (0.6, 2.4, 3.3):
            i = int(ms * RATE)
            seg = _lowpass(_noise(int(0.18 * RATE), int(ms * 10)), 1800.0) * \
                np.exp(-np.arange(int(0.18 * RATE)) / (0.035 * RATE))
            clank[i:i + len(seg)] += seg * 0.35
        x = (rumble + diesel + clank) * _env(n, 0.4, 0.6)
        pcm = _stereo(x, 0.16, 31)
    elif name == "m6_room_tone":
        dur = 4.0
        n = int(RATE * dur)
        t = _t(n)
        hum = np.sin(2 * math.pi * 50.0 * t) * 0.035 + \
            np.sin(2 * math.pi * 100.0 * t) * 0.018
        hiss = _highpass(_noise(n, 41), 2400.0) * 0.03
        x = (hum + hiss) * _env(n, 0.3, 0.4)
        pcm = _stereo(x, 0.10, 41)
    else:
        raise ValueError("Unknown M6 stem: " + name)
    pcm[0] = 0.0
    pcm[-1] = 0.0
    pcm.setflags(write=False)
    return pcm


# ── foley ───────────────────────────────────────────────────────────────────
def _crunch(seed, dur=0.22, amp=0.8):
    n = int(dur * RATE)
    x = _highpass(_noise(n, seed), 700.0) * 0.7
    x *= np.exp(-np.arange(n) / (dur * RATE * 0.30))
    return x * amp


@lru_cache(maxsize=32)
def foley_pcm(name):
    if name == "m6_rotor_away":
        n = int(2.2 * RATE); t = _t(n)
        chop = 0.45 + 0.55 * np.abs(np.sin(2 * math.pi * 11.0 * t))
        x = _lowpass(_noise(n, 51), 260.0) * chop * np.exp(-t * 1.1)
        x += np.sin(2 * math.pi * (92 - t * 12) * t) * 0.05 * np.exp(-t * 1.4)
    elif name == "m6_jump":
        n = int(0.6 * RATE); t = _t(n)
        whoosh = _highpass(_noise(n, 61), 500.0) * np.exp(-t * 5.0) * 0.8
        thump = np.sin(2 * math.pi * (70 - t * 30) * t) * np.exp(-t * 8.0) * 0.5
        x = whoosh + thump
    elif name == "m6_wind_gust":
        n = int(1.6 * RATE); t = _t(n)
        x = _lowpass(_noise(n, 71), 520.0) * np.exp(-((t - 0.7) ** 2) / 0.16) * 1.1
    elif name == "m6_fall":
        n = int(1.4 * RATE); t = _t(n)
        x = _lowpass(_noise(n, 81), 700.0) * (0.5 + 0.5 * t / 1.4) * 0.9
    elif name == "m6_land":
        n = int(0.5 * RATE); t = _t(n)
        thump = np.sin(2 * math.pi * (60 - t * 25) * t) * np.exp(-t * 9.0)
        x = _mix(thump * 0.9, _crunch(82, 0.18, 0.6))
    elif name == "m6_heli_away":
        n = int(2.6 * RATE); t = _t(n)
        chop = 0.5 + 0.5 * np.abs(np.sin(2 * math.pi * 10.0 * t))
        x = (_lowpass(_noise(n, 91), 220.0) * chop
             + np.sin(2 * math.pi * 80 * t) * 0.04) * np.exp(-t * 0.9)
    elif name == "m6_boxcar_door":
        n = int(0.9 * RATE); t = _t(n)
        slide = _lowpass(_noise(n, 101), 1200.0) * np.exp(-t * 1.8) * 0.5
        clang = np.sin(2 * math.pi * 180 * t) * np.exp(-t * 9.0) * 0.55
        x = slide + clang
    elif name == "m6_breath":
        n = int(0.7 * RATE); t = _t(n)
        x = _lowpass(_noise(n, 111), 900.0) * np.exp(-((t - 0.22) ** 2) / 0.02) * 0.7
    elif name == "m6_paper":
        n = int(0.35 * RATE); t = _t(n)
        x = _highpass(_noise(n, 121), 1500.0) * np.exp(-t * 8.0) * 0.5
    elif name == "m6_page_turn":
        n = int(0.5 * RATE); t = _t(n)
        x = _highpass(_noise(n, 131), 1100.0) * \
            (np.exp(-((t - 0.15) ** 2) / 0.01) + 0.6 * np.exp(-((t - 0.3) ** 2) / 0.012))
    elif name == "m6_snow_step":
        x = _crunch(141, 0.26, 0.7)
        n = len(x)
        x[:int(0.03 * RATE)] *= np.linspace(0.0, 1.0, int(0.03 * RATE))
    elif name == "m6_notebook_close":
        n = int(0.35 * RATE); t = _t(n)
        x = np.sin(2 * math.pi * 120 * t) * np.exp(-t * 14.0) * 0.6 + \
            _lowpass(_noise(n, 151), 800.0) * np.exp(-t * 16.0) * 0.4
    elif name == "m6_terminal_beep":
        n = int(0.5 * RATE); t = _t(n)
        x = np.zeros(n)
        for on, dur, f in ((0.02, 0.09, 980.0), (0.17, 0.07, 1320.0)):
            i = int(on * RATE); k = int(dur * RATE)
            seg = np.sin(2 * math.pi * f * _t(k)) * _env(k, 0.004, 0.03)
            x[i:i + k] += seg * 0.5
        x *= np.exp(-t * 2.0)
    elif name == "m6_radio_static":
        n = int(0.8 * RATE); t = _t(n)
        nz = _highpass(_noise(n, 161), 1200.0)
        gate = (np.sin(2 * math.pi * 7.0 * t) > -0.2).astype(np.float64)
        x = nz * (0.5 + 0.5 * gate) * np.exp(-t * 2.1) * 0.6
        x += np.sin(2 * math.pi * 1400 * t) * np.exp(-t * 30.0) * 0.2
    elif name == "m6_rifle_crack":
        n = int(0.5 * RATE); t = _t(n)
        x = _lowpass(_noise(n, 171), 5200.0) * np.exp(-t * 28.0) * 1.2
        x += np.sin(2 * math.pi * 90 * t) * np.exp(-t * 12.0) * 0.5
    elif name == "m6_train_depart":
        n = int(3.5 * RATE); t = _t(n)
        x = _lowpass(_noise(n, 181), 180.0, 3) * \
            (0.35 + 0.65 * np.clip(t / 1.6, 0.0, 1.0)) * np.exp(-t * 0.28) * 1.3
        x += np.sin(2 * math.pi * (38 + 3 * t) * t) * 0.06
    elif name == "m6_doors_close":
        n = int(1.2 * RATE); t = _t(n)
        hiss = _highpass(_noise(n, 191), 1600.0) * np.exp(-t * 2.6) * 0.4
        clunk = np.sin(2 * math.pi * 95 * t) * np.exp(-((t - 0.75) ** 2) / 0.004) * 0.7
        x = hiss + clunk
    elif name == "m6_tinnitus":
        # The ring after the round: two close high partials that beat, swelling
        # in fast and bleeding off over about a second and a half.
        n = int(1.8 * RATE); t = _t(n)
        ring = np.sin(2 * math.pi * 6100 * t) * 0.20             + np.sin(2 * math.pi * 6350 * t) * 0.12
        x = ring * np.clip(t / 0.05, 0.0, 1.0) * np.exp(-t * 1.5)
    elif name == "m6_report_far":
        # The rifle's report arriving late over the yard: dull, with a tail.
        n = int(1.8 * RATE); t = _t(n)
        body = _lowpass(_noise(n, 201), 1500.0) * np.exp(-t * 4.0)
        boom = np.sin(2 * math.pi * (68 - t * 10) * t) * np.exp(-t * 5.0) * 0.5
        x = body + boom
        for delay, gain in ((0.23, 0.42), (0.51, 0.24), (0.86, 0.12)):
            k = int(delay * RATE)
            x[k:] += x[:-k] * gain
    elif name == "m6_body_thud":
        n = int(0.55 * RATE); t = _t(n)
        thump = np.sin(2 * math.pi * (58 - t * 26) * t) * np.exp(-t * 11.0) * 0.8
        x = _mix(thump, _crunch(211, 0.22, 0.45))
    elif name == "m6_whiz":
        # A round passing close: a fast rising-then-falling whistle with a snap.
        n = int(0.28 * RATE); t = _t(n)
        f = 3400 - 2200 * np.clip(t / 0.22, 0.0, 1.0)
        x = np.sin(2 * math.pi * np.cumsum(f) / RATE) * 0.30 * np.exp(-t * 11.0)
        x += _highpass(_noise(n, 221), 2200.0) * np.exp(-t * 26.0) * 0.5
    elif name == "m6_headshot":
        # A short bright tick for a head hit.
        n = int(0.20 * RATE); t = _t(n)
        x = np.sin(2 * math.pi * 1760 * t) * np.exp(-t * 28.0) * 0.5
        x += np.sin(2 * math.pi * 2640 * t) * np.exp(-t * 36.0) * 0.3
    elif name == "m6_tink":
        # A brass casing on concrete.
        n = int(0.22 * RATE); t = _t(n)
        x = (np.sin(2 * math.pi * 4300 * t) * 0.35
             + np.sin(2 * math.pi * 5750 * t) * 0.22) * np.exp(-t * 34.0)
    else:
        raise ValueError("Unknown M6 foley: " + name)

    x = np.asarray(x, dtype=np.float64)
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak > 0.85:
        x = x * (0.85 / peak)
    x = _fade_edges(x, 0.006)
    x = np.column_stack((x, x))
    x[0] = 0.0
    x[-1] = 0.0
    x.setflags(write=False)
    return x


GENERATORS = [(name, lambda name=name: _wav(stem_pcm(name))) for name in STEMS]
GENERATORS += [(name, lambda name=name: _wav(foley_pcm(name))) for name in FOLEY]


def scene_stems(scene):
    return SCENE_STEMS.get(str(scene or ""), ())


def _current_scene():
    try:
        from core.cutscene_registry import current_shot
        shot = current_shot() or {}
        return str(shot.get("scene") or "")
    except Exception:
        return ""


class M6FilmAudio:
    """Own only this film's channels; never touch unrelated music or VO."""

    def __init__(self, manager):
        self.manager = manager
        manager.register_lazy_generators(GENERATORS)
        self.channels = {}
        self.foley_channels = []
        self.scene = None
        self.closed = False
        self.paused = False

    def prepare(self):
        for name in STEMS + FOLEY:
            self.manager.get_sound(name)

    def track(self, channel):
        if channel is not None:
            self.foley_channels.append((channel, channel.get_sound()))

    def _stop_stems(self):
        for ch in self.channels.values():
            try:
                ch.stop()
            except Exception:
                pass
        self.channels.clear()

    def _start_scene(self, scene):
        self._stop_stems()
        for name in scene_stems(scene):
            sound = self.manager.get_sound(name)
            if sound is None:
                continue
            sound.set_volume(1.0)
            try:
                ch = sound.play(loops=-1)
            except Exception:
                ch = None
            if ch is not None:
                self.channels[name] = ch
        self.scene = scene

    def update(self, elapsed_ms):
        if self.closed or self.paused:
            return
        self.foley_channels = [(c, s) for c, s in self.foley_channels
                               if c.get_busy() and c.get_sound() is s]
        scene = _current_scene()
        if scene != self.scene:
            self._start_scene(scene)
        master = float(getattr(self.manager, "master_volume", 0.8))
        sfx = float(getattr(self.manager, "sfx_volume", 1.0))
        for name, ch in self.channels.items():
            ch.set_volume(max(0.0, min(1.0, master * sfx * _STEM_GAIN.get(name, 0.4))))

    def pause(self):
        self.paused = True
        for ch in list(self.channels.values()) + [c for c, s in self.foley_channels
                                                   if c.get_sound() is s]:
            if ch.get_busy():
                ch.pause()

    def resume(self):
        self.paused = False
        for ch in list(self.channels.values()) + [c for c, s in self.foley_channels
                                                   if c.get_sound() is s]:
            ch.unpause()

    def stop(self):
        if self.closed:
            return
        self.closed = True
        for ch in list(self.channels.values()) + [c for c, s in self.foley_channels
                                                   if c.get_sound() is s]:
            try:
                ch.stop()
            except Exception:
                pass
        self.channels.clear()
        self.foley_channels.clear()


class M6TrainAudio:
    """Interactive train scene: two loops plus shared weapon/foley one-shots.

    Same silent-safe contract as the film audio - every call is a no-op when
    the mixer has no device, and the scene owns only the channels it starts.
    """

    _LOOPS = (("m6_train_idle", 0.26), ("m6_wind_bed", 0.30))

    def __init__(self, manager):
        self.manager = manager
        manager.register_lazy_generators(GENERATORS)
        self.loops = {}
        self.one_shots = []
        self.paused = False
        self.closed = False

    def start(self):
        if self.closed:
            return
        for name, gain in self._LOOPS:
            sound = self.manager.get_sound(name)
            if sound is None:
                continue
            try:
                ch = sound.play(loops=-1)
            except Exception:
                ch = None
            if ch is not None:
                self._apply_loop_gain(name, gain)
                self.loops[name] = ch

    def _apply_loop_gain(self, name, gain):
        ch = self.loops.get(name)
        if ch is None:
            return
        master = float(getattr(self.manager, "master_volume", 0.8))
        sfx = float(getattr(self.manager, "sfx_volume", 1.0))
        try:
            ch.set_volume(max(0.0, min(1.0, master * sfx * gain)))
        except Exception:
            pass

    def _one(self, name, volume):
        try:
            ch = self.manager.play(name, volume=volume)
        except Exception:
            return
        if ch is not None:
            self.one_shots.append((ch, ch.get_sound()))
        if len(self.one_shots) > 24:
            self.one_shots = [(c, s) for c, s in self.one_shots
                              if c.get_busy() and c.get_sound() is s]

    def shot(self, suppressed=True):
        self._one("gunshot", 0.34 if suppressed else 0.7)

    def guard_shot(self):
        self._one("m6_rifle_crack", 0.42)

    def impact(self, on_enemy=False):
        self._one("bullet_impact_enemy" if on_enemy else "bullet_impact",
                  0.5 if on_enemy else 0.32)

    def dry(self):
        self._one("empty_click", 0.5)

    def reload(self):
        self._one("reload", 0.55)

    def crack(self):
        self._one("m6_rifle_crack", 0.95)

    def doors(self):
        self._one("m6_doors_close", 0.7)

    def depart(self):
        self._one("m6_train_depart", 0.85)

    def breath(self):
        self._one("m6_breath", 0.5)

    def whiz(self):
        self._one("m6_whiz", 0.4)

    def headshot(self):
        self._one("m6_headshot", 0.5)

    def tink(self):
        self._one("m6_tink", 0.28)

    def tinnitus(self):
        self._one("m6_tinnitus", 0.55)

    def report(self):
        self._one("m6_report_far", 0.7)

    def thud(self):
        self._one("m6_body_thud", 0.7)

    def pause(self):
        if self.paused or self.closed:
            return
        self.paused = True
        for ch in list(self.loops.values()):
            try:
                ch.pause()
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

    def stop(self):
        if self.closed:
            return
        self.closed = True
        for ch in list(self.loops.values()):
            try:
                ch.stop()
            except Exception:
                pass
        for ch, _s in self.one_shots:
            try:
                ch.stop()
            except Exception:
                pass
        self.loops.clear()
        self.one_shots.clear()
