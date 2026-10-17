"""Mission 5 sound design and cutscene-owned playback.

Use the game's shared audio palette rather than a separate synth soundtrack.
Stems are prewarmed before the cinematic clock; cue timing and channel
ownership remain local to this scene. No downloads or new dependencies.

Mission-owned (RPE6 D1): lives next to ``finale_script`` instead of inside the
shared ``audio`` package, and registers its lazy generators with the
AudioManager when ``FinaleAudio`` is created rather than being imported by
``audio.audio`` (no shared -> mission import).
"""
from functools import lru_cache
import io
import wave

import numpy as np
from engine.assets import load_sound as _load_sound  # RPE6 D5: raw loads via engine.assets

from .finale_script import DURATION_MS, LINES


RATE = 22050
STEMS = ('m5_quay_air', 'm5_shadow_score')
FOLEY = ('m5_wet_step', 'm5_roof_step', 'm5_sling', 'm5_door', 'm5_door_open',
         'm5_laser_switch', 'm5_radio_open', 'm5_radio_close', 'm5_thunder')
PALETTE = {
    'rain': '_gen_rain', 'wind': '_gen_wind', 'drone': '_gen_ambient_drone',
    'm5_wet_step': '_gen_footstep_wet', 'm5_roof_step': '_gen_footstep_walk',
    'm5_sling': '_gen_rifle_handle', 'm5_door': '_gen_door_rattle',
    'm5_door_open': '_gen_door_open', 'm5_laser_switch': '_gen_empty_click',
    'm5_radio_open': '_gen_squelch_head', 'm5_radio_close': '_gen_squelch_tail',
    'm5_thunder': '_gen_thunder_rumble',
}


def _wav(pcm):
    out = io.BytesIO()
    with wave.open(out, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(np.rint(np.clip(pcm, -.92, .92) * 32767).astype('<i2').tobytes())
    return out.getvalue()


def _smooth(t, a, b):
    q = np.clip((t - a) / (b - a), 0., 1.)
    return q * q * (3. - 2. * q)


def _fade(t, duration, attack=.02, release=.12):
    return _smooth(t, 0, attack) * (1 - _smooth(t, duration-release, duration-1/RATE))


def _palette_pcm(name):
    # lazy: audio.py registers these generators before its manager is built.
    from audio import audio as shared
    # Shared generators use LEGACY_RNG. Prewarming runs serially on the game
    # thread: preserve its exact state, including on a generation failure.
    state = shared._rng_legacy.getstate()
    try:
        shared._rng_legacy.seed(51000 + sum((i+1)*ord(c) for i,c in enumerate(name)))
        data = getattr(shared, PALETTE[name])()
    finally:
        shared._rng_legacy.setstate(state)
    with wave.open(io.BytesIO(data), 'rb') as w:
        if (w.getframerate(), w.getsampwidth(), w.getnchannels()) != (RATE, 2, 1):
            raise ValueError('Unexpected shared audio format: '+name)
        return np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.float64)/32767


def _bed(source, n):
    """Overlap the shared loop's existing edge fades, avoiding periodic gaps."""
    overlap = min(round(.24*RATE), len(source)//4)
    stride = len(source)-overlap
    out = np.zeros(n+len(source))
    for a in range(0, n, stride):
        out[a:a+len(source)] += source
    return out[:n]


def _stereo(x, width=.18):
    # Mostly coherent centre: natural width, without the old independent hiss.
    delayed = np.zeros_like(x)
    delay = round(.013*RATE)
    delayed[delay:] = x[:-delay]
    return np.column_stack((x, (1-width)*x+width*delayed))


def _duck(t):
    """Smooth authored dips even if the optional recorded voice is absent."""
    env = np.ones(len(t))
    for on, off, *_ in LINES:
        dip = _smooth(t, on/1000-.22, on/1000) * (1-_smooth(t, off/1000, off/1000+.45))
        env *= 1 - .56 * dip
    return env


@lru_cache(maxsize=2)
def stem_pcm(name):
    n = round(RATE * DURATION_MS / 1000)
    t = np.arange(n, dtype=np.float64) / RATE
    edge = _fade(t, DURATION_MS/1000, .65, 1.65)
    if name == STEMS[0]:
        # Match _set_ambience(.3) and AudioManager's rain/wind gain trims.
        x = .165*_bed(_palette_pcm('rain'), n) + .12*_bed(_palette_pcm('wind'), n)
        perspective = 1 + .18*_smooth(t, 6.2, 9.6) - .58*_smooth(t, 34.9, 35.4)
        pcm = _stereo(x, .24)
        pcm *= (edge*perspective*(.72+.28*_duck(t)))[:,None]
    elif name == STEMS[1]:
        # Keep the registered score key for compatibility, but use the game's
        # industrial drone, not a new D/A chord, minor-second beat or chimes.
        x = .18*_bed(_palette_pcm('drone'), n)
        tension = .35 + .65*_smooth(t, 5.2, 9.6)
        release = 1 - .55*_smooth(t, 29.6, 34.9)
        pcm = _stereo(x)
        pcm *= (edge*tension*release*_duck(t))[:,None]
    else:
        raise ValueError('Unknown M5 stem: '+name)
    pcm[0] = 0.; pcm[-1] = 0.
    pcm.setflags(write=False)
    return pcm


def foley_pcm(name):
    if name not in FOLEY:
        raise ValueError('Unknown M5 foley: '+name)
    x = _palette_pcm(name)
    gain = {'m5_wet_step':.85, 'm5_roof_step':.75, 'm5_sling':.45,
            'm5_door':.55, 'm5_door_open':.45, 'm5_laser_switch':.35,
            'm5_radio_open':.65, 'm5_radio_close':.65, 'm5_thunder':.9}[name]
    x *= gain
    if name == 'm5_door':
        # Preserve the authored contact time: the leaf hits 680 ms after cue.
        x = np.pad(x, (round(.68*RATE), 0))
    t = np.arange(len(x))/RATE
    # Only de-click the edges; retain short, dry gameplay transients. No
    # bespoke pitched footstep body, radio beep, or long stereo reflection.
    x *= _fade(t, len(x)/RATE, .001, min(.006, len(x)/RATE/4))
    pcm = np.column_stack((x,x))
    pcm[0] = 0.; pcm[-1] = 0.
    return pcm


GENERATORS = [(name, lambda name=name: _wav(stem_pcm(name))) for name in STEMS]
GENERATORS += [(name, lambda name=name: _wav(foley_pcm(name))) for name in FOLEY]


class FinaleAudio:
    """Own only this scene's channels; never pause/stop unrelated audio or VO."""
    def __init__(self, manager):
        self.manager = manager
        # The mission brings its own sounds: register them with the shared
        # manager here (idempotent) instead of audio.audio importing this module.
        manager.register_lazy_generators(GENERATORS)
        self.channels = {}
        self.foley_channels = []
        self.started = False
        self.closed = False
        self.paused = False
        self.last_ms = None
        self.seek_sounds = []

    def prepare(self):
        for name in STEMS + FOLEY:
            self.manager.get_sound(name)

    def track(self, channel):
        if channel is not None:
            self.foley_channels.append((channel, channel.get_sound()))

    def _tick_lines(self, t0, t1):
        """One key-tick per revealed non-space glyph, max 1/frame.

        Pace (50 ms/char) must stay identical to m5shadow3d._subtitle's
        char_idx so ticks land on the glyphs.
        """
        for on, off, _who, text in LINES:
            if on <= t1 < off:
                c0 = min(len(text), max(0, int((t0-on)/50)))
                c1 = min(len(text), max(0, int((t1-on)/50)))
                if c1 > c0 and text[c0:c1].strip():
                    try:
                        self.track(self.manager.play("type_tick", volume=0.11))
                    except Exception:
                        pass
                break

    def update(self, elapsed_ms):
        if self.closed or self.paused:
            return
        # Prune finished one-shots to avoid pausing reused automatic channels.
        self.foley_channels = [(c, s) for c, s in self.foley_channels
                               if c.get_busy() and c.get_sound() is s]
        if elapsed_ms >= DURATION_MS:
            self.stop()
            return
        seek = self.last_ms is not None and abs(elapsed_ms-self.last_ms) > 750
        if not self.started or seek:
            for ch in self.channels.values():
                ch.stop()
            self.channels.clear()
            self.seek_sounds.clear()
            self.started = True
            for name in STEMS:
                sound = self.manager.get_sound(name)
                if sound is None:
                    continue  # Silent/no-device mode still completes the film.
                if elapsed_ms > 100:
                    # Re-anchor continuous stems after a suspended window or
                    # late entry; never replay the opening or missed foley.
                    import pygame
                    a = max(0, round(elapsed_ms*RATE/1000))
                    try:
                        sound = _load_sound(io.BytesIO(_wav(stem_pcm(name)[a:])))
                    except pygame.error:
                        continue
                    self.seek_sounds.append(sound)
                sound.set_volume(1.)
                ch = sound.play()
                if ch is not None:
                    self.channels[name] = ch
            # Retry a missing free channel on the next frame, not every asset.
            self.started = len(self.channels) == len(STEMS)
        # Fire subtitle ticks only for a continuous frame step (never on seek).
        if self.last_ms is not None and not seek and elapsed_ms > self.last_ms:
            self._tick_lines(self.last_ms, elapsed_ms)
        self.last_ms = elapsed_ms
        for name, ch in self.channels.items():
            master = self.manager.master_volume
            scale = (getattr(self.manager,'_current_music_vol',.5) if name==STEMS[1]
                     else self.manager.sfx_volume)
            ch.set_volume(max(0.,min(1.,master*scale)))

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
            ch.stop()
        self.channels.clear()
        self.foley_channels.clear()
        self.seek_sounds.clear()
