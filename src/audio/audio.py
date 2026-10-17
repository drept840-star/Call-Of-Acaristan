
import pygame
from engine.assets import load_music as _load_music, load_sound as _load_sound  # RPE6 D5
import math
import random
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import struct
import io
import array
import time
import os

SAMPLE_RATE = 22050
MAX_AMP = 32767

def _arr(n):
    return array.array("h", [0]) * n

def _wav(samples):
    n = len(samples)
    data_size = n * 2
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 1))
    buf.write(struct.pack("<H", 1))
    buf.write(struct.pack("<I", SAMPLE_RATE))
    buf.write(struct.pack("<I", SAMPLE_RATE * 2))
    buf.write(struct.pack("<H", 2))
    buf.write(struct.pack("<H", 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(samples.tobytes())
    return buf.getvalue()

def _load(wav_bytes):
    return _load_sound(io.BytesIO(wav_bytes))

def _write(buf, samples, amp=1.0):
    for i in range(len(buf)):
        v = int(samples[i] * amp)
        buf[i] = max(-MAX_AMP, min(MAX_AMP, buf[i] + v))

def _sin(n, freq, amp=1.0, phase=0.0):
    a = _arr(n)
    step = 2 * math.pi * freq / SAMPLE_RATE
    sin = math.sin
    max_amp_amp = MAX_AMP * amp
    for i in range(n):
        a[i] = int(max_amp_amp * sin(phase))
        phase += step
    return a

def _noise(n, amp=1.0):
    a = _arr(n)
    max_amp_amp = MAX_AMP * amp
    for i in range(n):
        a[i] = int(max_amp_amp * (_rng_legacy.random() * 2 - 1))
    return a

def _env_linear(buf, start=1.0, end=0.0):
    n = len(buf)
    for i in range(n):
        t = start + (end - start) * (i / n)
        buf[i] = int(buf[i] * t)

def _env_exp(buf, start=1.0, end=0.001, rate=5.0):
    n = len(buf)
    for i in range(n):
        t = start * math.exp(-rate * i / n)
        if t < end:
            t = 0
        buf[i] = int(buf[i] * t)

def _env_adsr(buf, attack=0.1, decay=0.2, sustain=0.5, release=0.2, sus_level=0.6):
    n = len(buf)
    a_i = int(n * attack)
    d_i = int(n * decay)
    s_i = int(n * (1 - release))
    for i in range(n):
        if i < a_i:
            t = i / a_i
        elif i < a_i + d_i:
            t = 1.0 - (1.0 - sus_level) * ((i - a_i) / d_i)
        elif i < s_i:
            t = sus_level
        else:
            t = sus_level * (1.0 - (i - s_i) / (n - s_i))
        buf[i] = int(buf[i] * t)

def _mix(base, overlay, overlay_amp=1.0):
    for i in range(min(len(base), len(overlay))):
        v = int(overlay[i] * overlay_amp)
        base[i] = max(-MAX_AMP, min(MAX_AMP, base[i] + v))

def _sine_sweep(n, f_start, f_end, amp=1.0):
    a = _arr(n)
    phase = 0.0
    sin = math.sin
    max_amp_amp = MAX_AMP * amp
    for i in range(n):
        t = i / n
        freq = f_start + (f_end - f_start) * t
        a[i] = int(max_amp_amp * sin(phase))
        phase += 2 * math.pi * freq / SAMPLE_RATE
    return a

def _lowpass(buf, strength=0.3):
    prev = 0
    for i in range(len(buf)):
        prev = prev * (1 - strength) + buf[i] * strength
        buf[i] = int(prev)

def _harmonics(n, base_freq, amps, amp=1.0):
    a = _arr(n)
    for i, h_amp in enumerate(amps):
        if h_amp:
            h = _sin(n, base_freq * (i + 1), amp * h_amp)
            _mix(a, h)
    return a

# ── New Powerful DSP Helpers for 16-Bit DOS Style Sound Design ──

def _resonant_filter(buf, cutoff_hz, resonance=0.5, filter_type="low"):
    """
    Chamberlin State Variable Filter (SVF) for beautiful analog-sounding sweeps.
    resonance: damping Q factor from 0.0 (flat) to 0.95 (ringing self-oscillation)
    """
    n = len(buf)
    out = _arr(n)
    cutoff_hz = max(12, min(9500, cutoff_hz))
    
    # SVF coefficients
    f = 2.0 * math.sin(math.pi * cutoff_hz / SAMPLE_RATE)
    q = 2.0 * (1.0 - max(0.0, min(0.95, resonance)))
    
    low = 0.0
    band = 0.0
    
    for i in range(n):
        input_val = float(buf[i])
        high = input_val - low - q * band
        band += f * high
        low += f * band
        
        if filter_type == "low":
            val = low
        elif filter_type == "high":
            val = high
        elif filter_type == "band":
            val = band
        else: # notch
            val = high + low
            
        out[i] = int(max(-MAX_AMP, min(MAX_AMP, val)))
        
    for i in range(n):
        buf[i] = out[i]

def _fm(n, carrier_hz, carrier_amp, mod_hz, mod_index, decay_rate=0.0):
    """
    Two-Operator FM Synthesizer.
    Generates rich metallic, mechanical, brassy, or chest-pounding sounds.
    """
    buf = _arr(n)
    phase_c = 0.0
    phase_m = 0.0
    step_c = 2.0 * math.pi * carrier_hz / SAMPLE_RATE
    step_m = 2.0 * math.pi * mod_hz / SAMPLE_RATE
    
    sin = math.sin
    max_amp_camp = MAX_AMP * carrier_amp
    
    for i in range(n):
        mod_env = math.exp(-decay_rate * i / n) if decay_rate > 0 else 1.0
        current_mod_index = mod_index * mod_env
        
        # Modulator output
        mod_val = sin(phase_m)
        phase_m += step_m
        
        # Frequency modulation
        inst_freq_mod = current_mod_index * step_m * mod_val
        
        buf[i] = int(max_amp_camp * sin(phase_c))
        phase_c += step_c + inst_freq_mod
        
    return buf

def _apply_delay(buf, delay_ms, feedback=0.4, wet=0.3):
    """
    Feedback delay line to simulate space, echo, and acoustic room depth.
    """
    n = len(buf)
    delay_samples = int(SAMPLE_RATE * (delay_ms / 1000.0))
    if delay_samples <= 0 or delay_samples >= n:
        return
    
    history = [0.0] * delay_samples
    ptr = 0
    
    for i in range(n):
        dry = float(buf[i])
        delayed = history[ptr]
        
        # Calculate new delay state
        new_history = dry + feedback * delayed
        history[ptr] = max(-MAX_AMP, min(MAX_AMP, new_history))
        ptr = (ptr + 1) % delay_samples
        
        # Mix dry and wet signals
        mixed = dry * (1.0 - wet) + delayed * wet
        buf[i] = int(max(-MAX_AMP, min(MAX_AMP, mixed)))

def _soft_clip(buf, drive=1.0):
    """
    Cubic saturation model to add warmth, weight, and prevent harsh digital clipping.
    """
    for i in range(len(buf)):
        x = (buf[i] / MAX_AMP) * drive
        # Cubic soft clipper
        if x > 1.25:
            y = 1.0
        elif x < -1.25:
            y = -1.0
        else:
            y = x - (x**3) / 3.0
            y = y * 0.95
        buf[i] = int(max(-1.0, min(1.0, y)) * MAX_AMP)

def _offset_mix(base, overlay, offset=0, amp=1.0):
    for i in range(min(len(overlay), len(base) - offset)):
        if offset + i < 0:
            continue
        v = int(overlay[i] * amp)
        base[offset + i] = max(-MAX_AMP, min(MAX_AMP, base[offset + i] + v))

# ── Upgraded DOS/16-Bit Sound Generators ──

# ── v2 organic DSP helpers (SFX audit pass) ──────────────────────────────
# ADDITIVE ONLY. None of the legacy primitives above are modified, so every
# sound that already passed the audit renders byte-identically.
#
# Why these exist:
#   _noise() is white noise, which reads as "radiation"/ Geiger hiss when used
#   for ambience beds; _resonant_filter() at high Q rings like a bell, which is
#   what made the water/wet footsteps sound like jingles; and _lowpass() takes
#   an opaque "strength" that is easy to leave effectively bypassed (that is how
#   room_tone ended up as raw static). These helpers give natural spectral tilt,
#   non-ringing band-limiting, and cutoffs specified in Hz.

def _rnd(a, b):
    """Uniform random float in [a, b)."""
    return a + _rng_legacy.random() * (b - a)

def _pink(n, amp=1.0):
    """Pink (1/f) noise via Paul Kellet's refined method, peak-normalised so
    ``amp`` is the peak fraction. Natural spectral tilt - the fix for beds that
    previously read as hiss."""
    raw = [0.0] * n
    b0 = b1 = b2 = b3 = b4 = b5 = b6 = 0.0
    for i in range(n):
        w = _rng_legacy.random() * 2.0 - 1.0
        b0 = 0.99886 * b0 + w * 0.0555179
        b1 = 0.99332 * b1 + w * 0.0750759
        b2 = 0.96900 * b2 + w * 0.1538520
        b3 = 0.86650 * b3 + w * 0.3104856
        b4 = 0.55000 * b4 + w * 0.5329522
        b5 = -0.7616 * b5 - w * 0.0168980
        raw[i] = b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362
        b6 = w * 0.115926
    pk = max((abs(v) for v in raw), default=0.0) or 1.0
    a = _arr(n)
    k = MAX_AMP * amp / pk
    for i in range(n):
        a[i] = int(max(-MAX_AMP, min(MAX_AMP, raw[i] * k)))
    return a

def _brown(n, amp=1.0):
    """Brown/red noise (leaky-integrated white), peak-normalised. Very dark -
    used for room rumble and the low body of impacts."""
    raw = [0.0] * n
    last = 0.0
    for i in range(n):
        w = _rng_legacy.random() * 2.0 - 1.0
        last = (last + 0.02 * w) / 1.02
        raw[i] = last
    pk = max((abs(v) for v in raw), default=0.0) or 1.0
    a = _arr(n)
    k = MAX_AMP * amp / pk
    for i in range(n):
        a[i] = int(max(-MAX_AMP, min(MAX_AMP, raw[i] * k)))
    return a

def _lp(buf, cutoff_hz, poles=2):
    """Non-resonant lowpass, cutoff in Hz (cascaded one-poles). Cannot ring."""
    cutoff_hz = max(8.0, min(SAMPLE_RATE * 0.45, cutoff_hz))
    a = 1.0 - math.exp(-2.0 * math.pi * cutoff_hz / SAMPLE_RATE)
    for _ in range(poles):
        prev = 0.0
        for i in range(len(buf)):
            prev += a * (buf[i] - prev)
            buf[i] = int(prev)
    return buf

def _hp(buf, cutoff_hz, poles=1):
    """Non-resonant highpass, cutoff in Hz. Used to remove sub-sonic mud."""
    cutoff_hz = max(1.0, min(SAMPLE_RATE * 0.45, cutoff_hz))
    a = math.exp(-2.0 * math.pi * cutoff_hz / SAMPLE_RATE)
    for _ in range(poles):
        px = 0.0
        py = 0.0
        for i in range(len(buf)):
            x = float(buf[i])
            y = a * (py + x - px)
            px = x
            py = y
            buf[i] = int(max(-MAX_AMP, min(MAX_AMP, y)))
    return buf

def _bp(buf, lo_hz, hi_hz):
    """Band-limit by cascading non-resonant LP then HP. Deliberately no Q, so
    it cannot ring - high-Q resonant bandpass is what produced the jingles."""
    _lp(buf, hi_hz, 2)
    _hp(buf, lo_hz, 1)
    return buf

def _plate(n, f0, modes, amp=1.0, decay=24.0):
    """Inharmonic vibrating-plate modes with independent exponential decays
    (higher modes die faster, as in real sheet metal). ``modes`` is a list of
    (ratio, gain). Real metal, versus 2-op FM which yields one bell-like pair."""
    buf = _arr(n)
    for ratio, gain in modes:
        f = f0 * ratio
        if f >= SAMPLE_RATE * 0.45 or gain <= 0:
            continue
        p = _sin(n, f, 1.0, phase=_rng_legacy.random() * 2.0 * math.pi)
        _env_exp(p, gain, 0.0005, decay * (1.0 + 0.55 * (ratio - 1.0)))
        _mix(buf, p, amp)
    return buf

def _multitap(buf, times_ms, gains, wet=0.5):
    """Multi-tap echo. Irregular taps read as a real space (cave, warehouse);
    a single short feedback delay reads as a metallic comb filter instead."""
    n = len(buf)
    src = [float(buf[i]) for i in range(n)]
    acc = [0.0] * n
    gsum = sum(gains) or 1.0
    for t_ms, g in zip(times_ms, gains):
        d = int(SAMPLE_RATE * t_ms / 1000.0)
        if d <= 0 or d >= n:
            continue
        for i in range(n - d):
            acc[i + d] += src[i] * (g / gsum)
    for i in range(n):
        buf[i] = int(max(-MAX_AMP, min(MAX_AMP, src[i] + acc[i] * wet)))
    return buf

def _crackle(n, density, amp, lo_hz, hi_hz):
    """Impulsive crackle: sparse, short, band-limited noise grains at random
    offsets and levels. Used for metal buzz, debris and radio static."""
    buf = _arr(n)
    count = max(1, int((n / float(SAMPLE_RATE)) * density * 900.0))
    for _ in range(count):
        L = max(8, int(SAMPLE_RATE * _rnd(0.0006, 0.0035)))
        off = _rng_legacy.randint(0, max(0, n - L))
        if off + L > n:
            L = n - off
        if L <= 8:
            continue
        g = _pink(L, amp * _rnd(0.35, 1.0))
        _bp(g, lo_hz, hi_hz)
        _env_exp(g, 1.0, 0.001, _rnd(90.0, 260.0))
        _offset_mix(buf, g, off)
    return buf

def _match_rms(buf, target_dbfs):
    """Scale to a target RMS in dBFS so a rewritten sound keeps the same
    loudness in the game mix as the version it replaces. Peak-guarded."""
    n = len(buf)
    if n == 0:
        return buf
    rms = math.sqrt(sum(float(x) * x for x in buf) / n)
    if rms <= 0:
        return buf
    k = ((10.0 ** (target_dbfs / 20.0)) * MAX_AMP) / rms
    for i in range(n):
        buf[i] = int(max(-MAX_AMP, min(MAX_AMP, buf[i] * k)))
    return _guard_peak(buf)

def _match_peak(buf, peak_frac):
    """Scale to a target peak fraction. Used where the rewrite deliberately
    changes duration, so an RMS match would mis-scale the transient."""
    pk = max((abs(x) for x in buf), default=0)
    if pk <= 0:
        return buf
    k = (MAX_AMP * peak_frac) / pk
    for i in range(len(buf)):
        buf[i] = int(max(-MAX_AMP, min(MAX_AMP, buf[i] * k)))
    return buf

def _guard_peak(buf, limit=0.985):
    """Scale down only if over the limit, so impulsive rewrites cannot clip."""
    pk = max((abs(x) for x in buf), default=0)
    lim = MAX_AMP * limit
    if pk > lim and pk > 0:
        g = lim / pk
        for i in range(len(buf)):
            buf[i] = int(buf[i] * g)
    return buf


def _gen_gunshot_core(volume=1.0, lowpass_strength=0.0):
    """
    Layered gunshot: sharp transient crack → resonant muzzle blast → chest-hitting FM thump → metallic FM casing drop → simulated echo chamber delay.
    """
    dur = 0.85
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    # Layer 1: Ultra-sharp initial transient (1ms of noise)
    crack_n = int(SAMPLE_RATE * 0.001)
    crack = _noise(crack_n, 1.0 * volume)
    _mix(buf, crack)
    
    # Layer 2: Muzzle blast - mid-range noise, resonant lowpass filter
    blast_n = int(SAMPLE_RATE * 0.1)
    blast = _noise(blast_n, 0.78 * volume)
    _resonant_filter(blast, 800, 0.35, "low")
    _env_exp(blast, 1.0, 0.001, 24.0)
    _offset_mix(buf, blast, int(SAMPLE_RATE * 0.001))
    
    # Layer 3: Chest-hitting FM sub thump (Simulates raw kinetic pressure wave)
    thump = _fm(int(SAMPLE_RATE * 0.35), 55, 0.9 * volume, 110, 1.8, decay_rate=7.0)
    _env_exp(thump, 1.0, 0.001, 6.0)
    _offset_mix(buf, thump, int(SAMPLE_RATE * 0.003))
    
    # Layer 4: Upper-mid body crackle
    mid_n = int(SAMPLE_RATE * 0.15)
    mid = _noise(mid_n, 0.52 * volume)
    _resonant_filter(mid, 2200, 0.2, "low")
    _env_exp(mid, 1.0, 0.001, 15.0)
    _offset_mix(buf, mid, int(SAMPLE_RATE * 0.002))
    
    # Layer 5: Meaty body resonance (FM carrier 200Hz, modulated by 100Hz)
    body_n = int(SAMPLE_RATE * 0.18)
    body = _fm(body_n, 200, 0.36 * volume, 100, 0.8, decay_rate=12.0)
    _env_exp(body, 1.0, 0.001, 14.0)
    _offset_mix(buf, body, int(SAMPLE_RATE * 0.002))
    
    # Layer 6: Brass shell casing hitting floor (Realistic metallic ring via FM)
    casing_delay = int(SAMPLE_RATE * 0.4)
    casing_n = int(SAMPLE_RATE * 0.15)
    casing = _fm(casing_n, 5200, 0.18 * volume, 8200, 3.5, decay_rate=18.0)
    _env_exp(casing, 1.0, 0.001, 14.0)
    _offset_mix(buf, casing, casing_delay)
    
    # Feedback echo simulating tight indoor warehouse walls
    _apply_delay(buf, 120, feedback=0.35, wet=0.25)
    _apply_delay(buf, 45, feedback=0.2, wet=0.15)
    
    # Cubic saturation and limiting
    _soft_clip(buf, 1.45)
    _env_exp(buf, 1.0, 0.001, 1.4)
    
    if lowpass_strength > 0:
        _resonant_filter(buf, int(750 * (1.0 - lowpass_strength)), 0.1)
        
    return _wav(buf)

def _gen_gunshot():
    return _gen_gunshot_core(volume=1.0, lowpass_strength=0.0)

def _gen_gunshot_distant():
    """Muffled distant version: high-frequencies stripped, bass thuds enhanced."""
    return _gen_gunshot_core(volume=0.5, lowpass_strength=0.075)


def _gen_sniper_crack():
    """High-powered distant sniper rifle: supersonic snap + delayed heavy report."""
    n = int(SAMPLE_RATE * 1.15)
    buf = _arr(n)

    # Instant supersonic crack.
    snap = _noise(int(SAMPLE_RATE * 0.004), 0.98)
    _resonant_filter(snap, 4200, 0.18, "high")
    _env_exp(snap, 1.0, 0.001, 80.0)
    _mix(buf, snap)

    # Rifle report arrives a hair later.
    blast = _noise(int(SAMPLE_RATE * 0.16), 0.62)
    _resonant_filter(blast, 620, 0.38, "low")
    _env_exp(blast, 1.0, 0.001, 16.0)
    _offset_mix(buf, blast, int(SAMPLE_RATE * 0.035))

    # Distant valley/building slap echo.
    echo = _noise(int(SAMPLE_RATE * 0.34), 0.24)
    _resonant_filter(echo, 280, 0.35, "low")
    _env_exp(echo, 1.0, 0.001, 6.2)
    _offset_mix(buf, echo, int(SAMPLE_RATE * 0.19))

    # Low pressure bloom.
    sub = _fm(int(SAMPLE_RATE * 0.55), 45, 0.34, 22, 0.7, decay_rate=4.8)
    _env_exp(sub, 1.0, 0.001, 5.0)
    _offset_mix(buf, sub, int(SAMPLE_RATE * 0.045))

    _apply_delay(buf, 170, feedback=0.26, wet=0.18)
    _soft_clip(buf, 1.45)
    _env_exp(buf, 1.0, 0.001, 1.25)
    return _wav(buf)


def _gen_bullet_snap():
    """Terrifying near-miss whip/snap passing the listener."""
    n = int(SAMPLE_RATE * 0.22)
    buf = _arr(n)
    zip1 = _sine_sweep(int(SAMPLE_RATE * 0.07), 6200, 1700, 0.42)
    _env_exp(zip1, 1.0, 0.001, 18.0)
    _mix(buf, zip1)
    grit = _noise(int(SAMPLE_RATE * 0.035), 0.34)
    _resonant_filter(grit, 5200, 0.2, "high")
    _env_exp(grit, 1.0, 0.001, 55.0)
    _offset_mix(buf, grit, int(SAMPLE_RATE * 0.006))
    tail = _sine_sweep(int(SAMPLE_RATE * 0.12), 1800, 520, 0.16)
    _env_exp(tail, 1.0, 0.001, 13.0)
    _offset_mix(buf, tail, int(SAMPLE_RATE * 0.035))
    _soft_clip(buf, 1.2)
    return _wav(buf)


def _gen_concrete_impact():
    """Heavy concrete bullet strike with debris scatter."""
    n = int(SAMPLE_RATE * 0.32)
    buf = _arr(n)
    hit = _noise(int(SAMPLE_RATE * 0.028), 0.92)
    _resonant_filter(hit, 760, 0.42, "low")
    _env_exp(hit, 1.0, 0.001, 28.0)
    _mix(buf, hit)
    crunch = _noise(int(SAMPLE_RATE * 0.18), 0.38)
    _resonant_filter(crunch, 420, 0.55)
    _env_exp(crunch, 1.0, 0.001, 9.5)
    _offset_mix(buf, crunch, int(SAMPLE_RATE * 0.012))
    for off_ms in (38, 74, 112):
        chip = _noise(int(SAMPLE_RATE * 0.018), 0.22)
        _resonant_filter(chip, 2400, 0.25, "high")
        _env_exp(chip, 1.0, 0.001, 36.0)
        _offset_mix(buf, chip, int(SAMPLE_RATE * off_ms / 1000))
    _soft_clip(buf, 1.35)
    return _wav(buf)


def _gen_tinnitus():
    """Post-near-miss ear ringing with slow fade."""
    n = int(SAMPLE_RATE * 2.1)
    buf = _arr(n)
    tone = _sin(n, 3180, 0.24)
    wobble = _sin(n, 7.0, 0.06)
    for i in range(n):
        # Amplitude shimmer, intentionally uncomfortable but not too loud.
        amp = 0.72 + 0.28 * math.sin(i * 0.004)
        buf[i] = int(tone[i] * amp + wobble[i] * 0.2)
    _env_adsr(buf, 0.02, 0.18, 0.42, 0.58, 0.72)
    _soft_clip(buf, 1.05)
    return _wav(buf)


def _gen_rifle_handle():
    """Small metallic rifle handling tick for origin reveal tension."""
    n = int(SAMPLE_RATE * 0.14)
    buf = _arr(n)
    for off_ms, freq in [(0, 1800), (38, 2600), (82, 1200)]:
        click = _fm(int(SAMPLE_RATE * 0.025), freq, 0.22, freq * 1.6, 2.4, decay_rate=35.0)
        _env_exp(click, 1.0, 0.001, 42.0)
        _offset_mix(buf, click, int(SAMPLE_RATE * off_ms / 1000))
    _soft_clip(buf, 1.1)
    return _wav(buf)


def _gen_footstep_variant(pitch_mul=1.0, amp=0.3, dur=0.045):
    """Foley style walk steps: punchy, organic, and clean of boxiness."""
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    # Heel strike: FM low-frequency thump (removes paper-thin sound)
    thump = _fm(n, int(82 * pitch_mul), amp, int(41 * pitch_mul), 0.5, decay_rate=16.0)
    _env_exp(thump, 1.0, 0.001, 28.0)
    
    # Friction texture: brief filtered noise
    grit = _noise(n, amp * 0.32)
    _resonant_filter(grit, 450, 0.2)
    _env_exp(grit, 1.0, 0.001, 32.0)
    
    # Toe-off tap transient
    click_n = min(n, int(SAMPLE_RATE * 0.008))
    click = _noise(click_n, amp * 0.45)
    _resonant_filter(click, 1800, 0.15)
    _env_exp(click, 1.0, 0.001, 60.0)
    
    _mix(buf, thump)
    _mix(buf, grit)
    _offset_mix(buf, click, 0)
    
    _soft_clip(buf, 1.1)
    return _wav(buf)

def _gen_footstep():
    return _gen_footstep_variant(pitch_mul=1.05, amp=0.78, dur=0.046)

def _gen_footstep_b():
    """Heavier boot step: deeper FM thump, wider gravel scrape."""
    n = int(SAMPLE_RATE * 0.055)
    buf = _arr(n)
    thump = _fm(n, 70, 0.38, 35, 0.7, decay_rate=15.0)
    _env_exp(thump, 1.0, 0.001, 22.0)
    
    slap = _noise(n, 0.32)
    _resonant_filter(slap, 320, 0.15)
    _env_exp(slap, 1.0, 0.001, 26.0)
    
    _mix(buf, thump)
    _mix(buf, slap)
    _soft_clip(buf, 1.15)
    return _wav(buf)

def _gen_footstep_c():
    """Light quick sneaker tap."""
    n = int(SAMPLE_RATE * 0.038)
    buf = _arr(n)
    thump = _fm(n, 105, 0.3, 52, 0.4, decay_rate=25.0)
    _env_exp(thump, 1.0, 0.001, 32.0)
    
    click = _noise(n, 0.38)
    _resonant_filter(click, 1400, 0.3)
    _env_exp(click, 1.0, 0.001, 45.0)
    
    _mix(buf, thump)
    _mix(buf, click)
    _soft_clip(buf, 1.1)
    return _wav(buf)

def _gen_footstep_walk_variant(pitch_mul=1.0, amp=0.22, dur=0.060):
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    thump = _fm(n, int(76 * pitch_mul), amp * 0.6, int(38 * pitch_mul), 0.3, decay_rate=18.0)
    _env_exp(thump, 1.0, 0.001, 18.0)
    
    scruff = _noise(n, amp * 0.42)
    _resonant_filter(scruff, 380, 0.1)
    _env_exp(scruff, 1.0, 0.001, 20.0)
    
    _mix(buf, thump)
    _mix(buf, scruff)
    _soft_clip(buf, 1.0)
    return _wav(buf)

def _gen_footstep_walk():
    return _gen_footstep_walk_variant(pitch_mul=1.0, amp=0.52, dur=0.060)

def _gen_footstep_walk_b():
    n = int(SAMPLE_RATE * 0.065)
    buf = _arr(n)
    thump = _fm(n, 62, 0.22, 31, 0.3, decay_rate=12.0)
    _env_exp(thump, 1.0, 0.001, 15.0)
    
    scruff = _noise(n, 0.28)
    _resonant_filter(scruff, 280, 0.1)
    _env_exp(scruff, 1.0, 0.001, 18.0)
    
    _mix(buf, thump)
    _mix(buf, scruff)
    return _wav(buf)

def _gen_footstep_walk_c():
    """Walk variant 3 (v2): a soft heel-toe rolling step with a distinct cloth
    scuff tail. Previously an 88 Hz hit at 0.050 s measuring -36.2 dBFS - about
    5 dB below its own family and 16 dB below the ~-20 dBFS target documented
    above, so it was effectively inaudible in play. Now level-matched to the
    walk family and different in shape, not just pitch."""
    n = int(SAMPLE_RATE * 0.078)
    buf = _arr(n)

    # heel down first
    heel = _brown(int(SAMPLE_RATE * 0.032), 0.46)
    _lp(heel, 215, 2)
    _env_exp(heel, 1.0, 0.001, 32.0)
    _offset_mix(buf, heel, 0)

    # then the toe rolling off - this two-part shape is the difference
    toe = _pink(int(SAMPLE_RATE * 0.024), 0.32)
    _bp(toe, 380, 1900)
    _env_exp(toe, 1.0, 0.001, 46.0)
    _offset_mix(buf, toe, int(SAMPLE_RATE * 0.038))

    # cloth/scuff tail across the whole step
    scuff = _pink(n, 0.17)
    _bp(scuff, 900, 3800)
    _env_adsr(scuff, 0.30, 0.30, 0.50, 0.35, 0.40)
    _mix(buf, scuff, 0.70)

    _soft_clip(buf, 1.05)
    # level-matched to the walk family median (-31.0 dBFS), not its old -36.2
    return _wav(_match_rms(buf, -31.0))



# ── Overhaul: surface-specific footsteps, NPC feet, foley, ambience layers ──
# Registered LAZILY (see LAZY_GENS / AudioManager._ensure) so startup synthesis
# cost stays flat; each buffer is built once, on first use.
# Level note: foot families are synthesized HOT (target ~-20 dBFS RMS at source)
# because play-time volume and master volume multiply down from here. An early
# pass sat at -30..-47 dBFS and was inaudible in play.
def _gen_footstep_metal_variant(pitch_mul=1.0, amp=0.75, dur=0.090):
    """Hollow clang: two FM partials with a real ring tail + bright tick."""
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    clang = _fm(n, int(210 * pitch_mul), amp * 0.85, int(63 * pitch_mul), 2.2, decay_rate=6.0)
    _env_exp(clang, 1.0, 0.001, 7.0)
    partial = _fm(n, int(560 * pitch_mul), amp * 0.30, int(112 * pitch_mul), 1.6, decay_rate=8.0)
    _env_exp(partial, 1.0, 0.001, 9.0)
    body = _noise(n, amp * 0.35)
    _resonant_filter(body, 900, 0.3)
    _env_exp(body, 1.0, 0.001, 26.0)
    tick = _noise(min(n, int(SAMPLE_RATE * 0.012)), amp * 0.9)
    _resonant_filter(tick, 3000, 0.5, "high")
    _env_exp(tick, 1.0, 0.001, 55.0)
    _mix(buf, clang)
    _mix(buf, partial)
    _mix(buf, body)
    _offset_mix(buf, tick, 0)
    _soft_clip(buf, 1.2)
    return _wav(buf)

def _gen_footstep_metal():
    return _gen_footstep_metal_variant(1.0)

def _gen_footstep_metal_b():
    """Metal variant 2 (v2): a hollow deck-plate step with a longer, more
    resonant ring tail, a lighter top-end tick and its own mode set. Previously
    this was variant 1 pitched up 14%, so it differed only in tuning - now it is
    a different plate being struck."""
    n = int(SAMPLE_RATE * 0.115)
    buf = _arr(n)

    # hollow deck plate - lower fundamental, longer decay than variant 1
    plate = _plate(n, 268.0,
                   [(1.0, 1.0), (2.41, 0.48), (3.90, 0.26), (6.10, 0.13), (8.7, 0.06)],
                   0.52, decay=9.0)
    _mix(buf, plate)

    body = _pink(n, 0.30)
    _bp(body, 380, 2200)
    _env_exp(body, 1.0, 0.001, 30.0)
    _mix(buf, body)

    tick = _pink(int(SAMPLE_RATE * 0.006), 0.55)
    _bp(tick, 2600, 7000)
    _env_exp(tick, 1.0, 0.001, 150.0)
    _offset_mix(buf, tick, 0)

    thud = _brown(int(SAMPLE_RATE * 0.050), 0.46)
    _lp(thud, 195, 2)
    _env_exp(thud, 1.0, 0.001, 26.0)
    _mix(buf, thud)

    _soft_clip(buf, 1.18)
    return _wav(_match_rms(buf, -17.5))


def _gen_footstep_metal_c():
    return _gen_footstep_metal_variant(0.88)

def _gen_footstep_grate_variant(pitch_mul=1.0, amp=0.95, dur=0.070):
    """Loose metal grate, v4: the concrete step, heavier and darker, plus a
    strictly low-passed loose-bar rattle.

    v1 rang (bell), v2 clicked (jingle bells), v3 hissed (2.3 kHz flutter -
    still a jingle, sizzlier). All three invented a new metallic voice and all
    three were wrong. v4 invents nothing: it reuses the concrete step body the
    player already accepts, pitched down, and adds rattle energy ONLY below
    ~500 Hz (two one-pole passes at strength 0.10). No clang partial, no
    flutter, no click train, no delay, no resonant band.
    """
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    thump = _fm(n, int(70 * pitch_mul), amp, int(35 * pitch_mul), 0.5, decay_rate=18.0)
    _env_exp(thump, 1.0, 0.001, 20.0)
    grit = _noise(n, amp * 0.40)
    _resonant_filter(grit, 380, 0.2)
    _env_exp(grit, 1.0, 0.001, 26.0)
    rat_n = int(SAMPLE_RATE * 0.035)
    rat = _noise(rat_n, amp * 0.34)
    _lowpass(rat, 0.10)
    _lowpass(rat, 0.10)
    _env_exp(rat, 1.0, 0.001, 34.0)
    _mix(buf, thump)
    _mix(buf, grit)
    _offset_mix(buf, rat, int(SAMPLE_RATE * 0.004))
    _soft_clip(buf, 1.1)
    return _wav(buf)


def _gen_footstep_grate():
    return _gen_footstep_grate_variant(1.0)

def _gen_footstep_grate_b():
    return _gen_footstep_grate_variant(1.12)

def _gen_footstep_wet_variant(pitch_mul=1.0, amp=0.50, dur=0.078):
    """Damp concrete (v2): a muffled low step, a wet squelch from band-limited
    noise and a soft suction release. The old version's "slap" was noise through
    a resonant highpass at 1.5 kHz and its suction was a tonal sine sweep - both
    ring, which is what made it jingle."""
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)

    # muffled step body
    step = _brown(n, amp * 1.15)
    _lp(step, 205 * pitch_mul, 2)
    _env_exp(step, 1.0, 0.001, 20.0)
    _mix(buf, step)

    # wet squelch: band-limited noise with a soft envelope, no Q
    sq = _pink(n, amp * 0.62)
    _bp(sq, 300 * pitch_mul, 1850 * pitch_mul)
    _env_adsr(sq, 0.07, 0.35, 0.50, 0.40, 0.50)
    _mix(buf, sq)

    # suction on toe-off: a dark noise swell, not a tuned sweep
    su_n = min(n, int(SAMPLE_RATE * 0.036))
    su = _pink(su_n, amp * 0.42)
    _bp(su, 240, 1150)
    _env_adsr(su, 0.45, 0.20, 0.50, 0.35, 0.40)
    _offset_mix(buf, su, min(int(SAMPLE_RATE * 0.030), max(0, n - su_n)))

    _lp(buf, 4200, 1)
    _soft_clip(buf, 1.08)
    return _wav(_match_rms(buf, -17.9))


def _gen_footstep_wet():
    return _gen_footstep_wet_variant(1.0)

def _gen_footstep_wet_b():
    return _gen_footstep_wet_variant(1.1)

def _gen_footstep_water_variant(pitch_mul=1.0, amp=0.60, dur=0.115):
    """Shallow puddle (v2): a broadband displacement splash, a low water body
    and irregular droplet grains. The old version pushed its droplets through a
    resonant highpass at 2.4 kHz, added a tonal sine sweep, and ran a 30 ms
    feedback delay at 0.55 wet - all three ring, which is why it read as a
    jingle instead of water."""
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)

    # displacement: band-limited "shhh" with a natural attack/decay, no Q
    sp = min(int(SAMPLE_RATE * 0.048), n)
    splash = _pink(sp, amp * 0.95)
    _bp(splash, 680 * pitch_mul, 6200 * pitch_mul)
    _env_adsr(splash, 0.08, 0.30, 0.50, 0.45, 0.55)
    _offset_mix(buf, splash, 0)

    # low water body - the foot actually pushing mass aside
    body = _brown(n, amp * 0.60)
    _lp(body, 245 * pitch_mul, 2)
    _env_exp(body, 1.0, 0.001, 26.0)
    _mix(buf, body)

    # droplets: randomised noise grains, deliberately never resonant
    for _ in range(5):
        L = int(SAMPLE_RATE * _rnd(0.003, 0.008))
        off = int(SAMPLE_RATE * _rnd(0.034, 0.098))
        if off + L >= n:
            continue
        d = _pink(L, amp * _rnd(0.20, 0.46))
        _bp(d, _rnd(1300, 3500) * pitch_mul, _rnd(5000, 8000))
        _env_exp(d, 1.0, 0.001, _rnd(95.0, 165.0))
        _offset_mix(buf, d, off)

    _lp(buf, 8000, 1)
    _soft_clip(buf, 1.08)
    return _wav(_match_rms(buf, -15.45))


def _gen_footstep_water():
    return _gen_footstep_water_variant(1.0)

def _gen_footstep_water_b():
    return _gen_footstep_water_variant(0.9)

def _gen_footstep_debris_variant(pitch_mul=1.0, amp=0.62, dur=0.080):
    """Rubble: band scuff, low crunch, granular clicks."""
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    scuff = _noise(n, amp * 0.95)
    _resonant_filter(scuff, 700 * pitch_mul, 0.35)
    _env_exp(scuff, 1.0, 0.001, 14.0)
    crunch = _fm(n, int(120 * pitch_mul), amp * 0.75, int(41 * pitch_mul), 0.8, decay_rate=10.0)
    _env_exp(crunch, 1.0, 0.001, 16.0)
    _mix(buf, scuff)
    _mix(buf, crunch)
    for off in (int(SAMPLE_RATE * 0.010), int(SAMPLE_RATE * 0.028),
                int(SAMPLE_RATE * 0.046), int(SAMPLE_RATE * 0.061)):
        click = _noise(int(SAMPLE_RATE * 0.006), amp * 0.95)
        _resonant_filter(click, 2100 * pitch_mul, 0.4, "high")
        _env_exp(click, 1.0, 0.001, 50.0)
        _offset_mix(buf, click, off)
    _soft_clip(buf, 1.1)
    return _wav(buf)

def _gen_footstep_debris():
    return _gen_footstep_debris_variant(1.0)

def _gen_footstep_debris_b():
    return _gen_footstep_debris_variant(1.15)

def _gen_enemy_footstep_variant(pitch_mul=1.0, amp=0.80, dur=0.075):
    """Boots: heavier than the player, heel click, faint webbing jingle."""
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    thump = _fm(n, int(66 * pitch_mul), amp, int(33 * pitch_mul), 0.5, decay_rate=15.0)
    _env_exp(thump, 1.0, 0.001, 17.0)
    heel = _noise(int(SAMPLE_RATE * 0.010), amp * 0.8)
    _resonant_filter(heel, 1200, 0.25)
    _env_exp(heel, 1.0, 0.001, 48.0)
    jingle = _fm(n, int(1400 * pitch_mul), amp * 0.22, 9, 0.6, decay_rate=9.0)
    _mix(buf, thump)
    _offset_mix(buf, heel, 0)
    _mix(buf, jingle)
    _soft_clip(buf, 1.2)
    return _wav(buf)

def _gen_enemy_footstep():
    return _gen_enemy_footstep_variant(1.0)

def _gen_enemy_footstep_b():
    return _gen_enemy_footstep_variant(1.1)

def _gen_enemy_footstep_c():
    """Enemy boot variant 3 (v2): a dragging boot - heavier, duller, with a
    heel scuff that trails behind the strike and a faint gear rattle. Previously
    variant 1 pitched down 10%, so it differed only in tuning."""
    n = int(SAMPLE_RATE * 0.095)
    buf = _arr(n)

    thump = _brown(n, 0.88)
    _lp(thump, 152, 2)
    _env_exp(thump, 1.0, 0.001, 19.0)
    _mix(buf, thump)

    heel = _pink(int(SAMPLE_RATE * 0.013), 0.52)
    _bp(heel, 480, 2300)
    _env_exp(heel, 1.0, 0.001, 82.0)
    _offset_mix(buf, heel, 0)

    # the drag: noise band that trails AFTER the strike
    drag = _pink(int(SAMPLE_RATE * 0.058), 0.30)
    _bp(drag, 290, 1650)
    _env_adsr(drag, 0.25, 0.30, 0.55, 0.35, 0.50)
    _offset_mix(buf, drag, int(SAMPLE_RATE * 0.020))

    # webbing / kit jingle, kept faint and non-tonal
    gear = _crackle(int(SAMPLE_RATE * 0.030), 0.26, 0.11, 2500, 6400)
    _offset_mix(buf, gear, int(SAMPLE_RATE * 0.006))

    _soft_clip(buf, 1.15)
    return _wav(_match_rms(buf, -15.7))


def _gen_volkov_step():
    """Heavy coat-and-boot step with a swish, softer top end."""
    n = int(SAMPLE_RATE * 0.095)
    buf = _arr(n)
    thump = _fm(n, 58, 0.80, 29, 0.5, decay_rate=13.0)
    _env_exp(thump, 1.0, 0.001, 15.0)
    heel = _noise(int(SAMPLE_RATE * 0.009), 0.45)
    _resonant_filter(heel, 900, 0.25)
    _env_exp(heel, 1.0, 0.001, 45.0)
    swish = _noise(n, 0.22)
    _lowpass(swish, 0.4)
    _env_exp(swish, 0.6, 0.001, 11.0)
    _mix(buf, thump)
    _offset_mix(buf, heel, 0)
    _mix(buf, swish)
    _soft_clip(buf, 1.1)
    return _wav(buf)

def _gen_detainee_shuffle():
    """Bare/shod shuffle, no heel: two soft scuffs (present but quiet)."""
    n = int(SAMPLE_RATE * 0.100)
    buf = _arr(n)
    a = _noise(int(SAMPLE_RATE * 0.030), 0.30)
    _resonant_filter(a, 500, 0.2)
    _env_exp(a, 1.0, 0.001, 16.0)
    b = _noise(int(SAMPLE_RATE * 0.026), 0.24)
    _resonant_filter(b, 620, 0.2)
    _env_exp(b, 1.0, 0.001, 16.0)
    _mix(buf, a)
    _offset_mix(buf, b, int(SAMPLE_RATE * 0.045))
    _soft_clip(buf, 0.9)
    return _wav(buf)

def _gen_boot_step_tile():
    """Hard heel on tile with a short room echo."""
    n = int(SAMPLE_RATE * 0.060)
    buf = _arr(n)
    heel = _fm(n, 95, 0.95, 47, 0.4, decay_rate=20.0)
    _env_exp(heel, 1.0, 0.001, 22.0)
    tap = _noise(int(SAMPLE_RATE * 0.008), 0.80)
    _resonant_filter(tap, 2400, 0.3, "high")
    _env_exp(tap, 1.0, 0.001, 70.0)
    _mix(buf, heel)
    _offset_mix(buf, tap, 0)
    _apply_delay(buf, 40, 0.3, 0.5)
    _soft_clip(buf, 1.2)
    return _wav(buf)

def _gen_chair_drag():
    """Stick-slip wood drag with a low groan."""
    n = int(SAMPLE_RATE * 0.350)
    buf = _arr(n)
    drag = _noise(n, 0.20)
    _resonant_filter(drag, 480, 0.3)
    _env_adsr(drag, 0.10, 0.2, 0.7, 0.3, 0.6)
    groan = _fm(n, 90, 0.14, 7, 1.2, decay_rate=3.0)
    _mix(buf, drag)
    _mix(buf, groan)
    for off in (int(SAMPLE_RATE * 0.08), int(SAMPLE_RATE * 0.19)):
        bump = _noise(int(SAMPLE_RATE * 0.012), 0.22)
        _resonant_filter(bump, 700, 0.35)
        _env_exp(bump, 1.0, 0.001, 40.0)
        _offset_mix(buf, bump, off)
    _soft_clip(buf, 1.0)
    return _wav(buf)

def _gen_chair_scrape_short():
    n = int(SAMPLE_RATE * 0.120)
    buf = _arr(n)
    drag = _noise(n, 0.22)
    _resonant_filter(drag, 620, 0.35)
    _env_exp(drag, 1.0, 0.001, 14.0)
    _mix(buf, drag)
    _soft_clip(buf, 1.0)
    return _wav(buf)

def _seamless_loop(buf, ms=80):
    """Fold the tail into the head so a looped bed has no 2-second seam click."""
    n = len(buf)
    m = int(SAMPLE_RATE * ms / 1000.0)
    if n <= 2 * m:
        return buf
    out = buf[:n - m]
    for i in range(m):
        t = i / float(m)
        out[i] = int(buf[i] * t + buf[n - m + i] * (1.0 - t))
    return out


def _gen_room_tone():
    """Interior bed (v2): dark brown-noise rumble confined well below the hiss
    band, a faint HVAC presence, and mains hum with harmonics. The old version
    was white noise through _lowpass(strength=0.75) - a coefficient that high is
    effectively a bypass, which is precisely why it read as static."""
    n = int(SAMPLE_RATE * 2.0)
    buf = _brown(n, 0.34)
    _lp(buf, 250, 3)                 # room tone lives under ~300 Hz
    _hp(buf, 22, 1)

    # faint HVAC band so the room is not only sub-bass
    hv = _pink(n, 0.055)
    _bp(hv, 190, 680)
    _mix(buf, hv, 0.60)

    # mains hum + harmonics (a real room always has these)
    _mix(buf, _sin(n, 50.0, 0.030))
    _mix(buf, _sin(n, 100.0, 0.012))
    _mix(buf, _sin(n, 150.0, 0.005))
    return _wav(_match_rms(_seamless_loop(buf), -34.8))


def _gen_elec_hum():
    """Transformer/relay proximity hum with coil whine, loopable."""
    n = int(SAMPLE_RATE * 2.0)
    buf = _harmonics(n, 100.0, [0.0, 0.035, 0.015, 0.007])
    whine = _fm(n, 3100.0, 0.003, 5.0, 0.3)
    _mix(buf, whine)
    return _wav(buf)

def _gen_rain_inside():
    """Exterior rain heard through a roof: muffled, loopable."""
    n = int(SAMPLE_RATE * 2.0)
    buf = _noise(n, 0.16)
    _resonant_filter(buf, 900, 0.25, "low")
    _lowpass(buf, 0.5)
    return _wav(_seamless_loop(buf))

def _gen_wind_gust():
    """Slow, deep, exterior-only swell. Fast/bright gusts read as static."""
    n = int(SAMPLE_RATE * 1.8)
    buf = _noise(n, 0.10)
    _resonant_filter(buf, 380, 0.3, "low")
    _lowpass(buf, 0.45)
    _env_adsr(buf, 0.5, 0.2, 0.8, 0.6, 0.5)
    return _wav(buf)

def _gen_drip_echo():
    """A water drip: fast plop + body resonance + one distant tile echo.

    The first synth was a 20 ms 1200->400 Hz sweep with a hot delay, which read
    as a sonar blip. Real drips are a ~12 ms plop falling in pitch, a short
    resonant body, and a single quiet reflection.
    """
    n = int(SAMPLE_RATE * 0.26)
    buf = _arr(n)
    plop = _sine_sweep(int(SAMPLE_RATE * 0.012), 1900, 650, 0.42)
    _env_exp(plop, 1.0, 0.001, 40.0)
    tick = _noise(int(SAMPLE_RATE * 0.003), 0.18)
    _resonant_filter(tick, 3000, 0.4, "high")
    body = _fm(int(SAMPLE_RATE * 0.05), 420, 0.12, 6, 0.8, decay_rate=22.0)
    _mix(buf, plop)
    _offset_mix(buf, tick, 0)
    _offset_mix(buf, body, int(SAMPLE_RATE * 0.004))
    _apply_delay(buf, 160, 0.25, 0.30)
    return _wav(buf)

def _gen_pa_chime():
    """Two-tone PA attention chime, muffled by a cheap speaker."""
    n = int(SAMPLE_RATE * 0.5)
    buf = _arr(n)
    a = _sin(int(SAMPLE_RATE * 0.16), 880.0, 0.12)
    _env_exp(a, 1.0, 0.05, 8.0)
    b = _sin(int(SAMPLE_RATE * 0.22), 660.0, 0.12)
    _env_exp(b, 1.0, 0.05, 7.0)
    _mix(buf, a)
    _offset_mix(buf, b, int(SAMPLE_RATE * 0.15))
    _resonant_filter(buf, 2400, 0.3, "low")
    _apply_delay(buf, 90, 0.25, 0.3)
    return _wav(buf)

def _gen_pa_mumble():
    """Unintelligible announcement burble through the PA."""
    n = int(SAMPLE_RATE * 1.2)
    buf = _noise(n, 0.07)
    _resonant_filter(buf, 1100, 0.5)
    # speech-like amplitude modulation ~4 Hz
    am = 2.0 * math.pi * 4.0 / SAMPLE_RATE
    for i in range(n):
        buf[i] = int(buf[i] * (0.35 + 0.65 * abs(math.sin(am * i))))
    _env_adsr(buf, 0.08, 0.1, 0.9, 0.25, 0.7)
    return _wav(buf)

def _gen_debris_settle():
    """Building cooling after an explosion: sparse granular ticks."""
    n = int(SAMPLE_RATE * 0.8)
    buf = _arr(n)
    for off in (int(SAMPLE_RATE * 0.05), int(SAMPLE_RATE * 0.22),
                int(SAMPLE_RATE * 0.41), int(SAMPLE_RATE * 0.63)):
        tick = _noise(int(SAMPLE_RATE * 0.006), 0.16)
        _resonant_filter(tick, 1800, 0.4, "high")
        _env_exp(tick, 1.0, 0.001, 60.0)
        _offset_mix(buf, tick, off)
    _apply_delay(buf, 120, 0.3, 0.3)
    return _wav(buf)

# Mission 4 arrest cues: isolated RNGs keep legacy sound variation unchanged.
def _m4_noise(n, rng, lo_hz, hi_hz, amp):
    buf = _arr(n)
    for i in range(n):
        buf[i] = int(MAX_AMP * 0.5 * rng.uniform(-1.0, 1.0))
    _bp(buf, lo_hz, hi_hz)
    return _match_peak(buf, amp)


def _m4_fade(buf, attack_s, release_s):
    attack = int(SAMPLE_RATE * attack_s)
    release = int(SAMPLE_RATE * release_s)
    for i in range(attack):
        gain = 0.5 - 0.5 * math.cos(math.pi * i / (attack - 1))
        buf[i] = int(buf[i] * gain)
    for i in range(release):
        gain = 0.5 - 0.5 * math.cos(math.pi * i / (release - 1))
        buf[-1 - i] = int(buf[-1 - i] * gain)
    return buf


def _gen_m4_tension():
    """Restrained bowed low cluster with a slowly building radio texture."""
    rng = random.Random(7401)
    n = int(SAMPLE_RATE * 7.6)
    buf = _arr(n)
    for idx, (freq, amp) in enumerate(((65.41, 0.075), (69.30, 0.048), (98.0, 0.026))):
        voice = _arr(n)
        for ratio, gain in ((1.0, 1.0), (2.002, 0.34), (3.003, 0.18),
                            (4.006, 0.075), (5.01, 0.032)):
            _mix(voice, _sin(n, freq * ratio, amp * gain,
                             phase=rng.uniform(0.0, 2.0 * math.pi)))
        for i in range(n):
            t = i / SAMPLE_RATE
            bow = (0.82 + 0.12 * math.sin(2.0 * math.pi * 0.23 * t + idx)
                   + 0.06 * math.sin(2.0 * math.pi * (4.6 + idx * 0.17) * t))
            voice[i] = int(voice[i] * bow)
        _m4_fade(voice, 0.8 + idx * 0.22, 0.7)
        _mix(buf, voice)

    _mix(buf, _m4_noise(n, rng, 170, 1000, 0.026))
    radio = _m4_noise(n, rng, 650, 2150, 0.018)
    for i in range(n):
        t = i / SAMPLE_RATE
        radio[i] = int(radio[i] * (0.65 + 0.23 * math.sin(2.0 * math.pi * 1.7 * t)
                                  + 0.12 * math.sin(2.0 * math.pi * 0.41 * t + 0.6)))
    _mix(buf, radio)
    for i in range(n):
        buf[i] = int(buf[i] * (0.16 + 0.72 * (i / (n - 1)) ** 1.25))
    return _wav(_match_peak(_m4_fade(buf, 1.15, 0.6), 0.28))


def _gen_m4_cuff_close():
    """Two small ratchet closures with damped metal teeth and quiet weight."""
    rng = random.Random(7402)
    n = int(SAMPLE_RATE * 0.6)
    buf = _arr(n)
    for start, level in ((0.075, 1.0), (0.295, 0.87)):
        rub = _m4_noise(int(SAMPLE_RATE * 0.07), rng, 400, 1700, 0.016 * level)
        _m4_fade(rub, 0.008, 0.024)
        _offset_mix(buf, rub, int(SAMPLE_RATE * (start - 0.035)))
        for tooth, gain in ((0.0, 0.65), (0.018, 0.85), (0.039, 1.0)):
            length = int(SAMPLE_RATE * 0.055)
            click = _m4_noise(length, rng, 900, 4200, 0.10 * level * gain)
            for freq, amp in ((1350, 0.095), (2400, 0.045), (3820, 0.018)):
                mode = _sin(length, freq * rng.uniform(0.98, 1.02), amp * level * gain,
                            phase=rng.uniform(0.0, 2.0 * math.pi))
                _env_exp(mode, 1.0, 0.0, 9.0)
                _mix(click, mode)
            _env_exp(click, 1.0, 0.0, 7.0)
            _m4_fade(click, 0.0008, 0.01)
            _offset_mix(buf, click, int(SAMPLE_RATE * (start + tooth)))
        weight = _sin(int(SAMPLE_RATE * 0.16), 185, 0.04 * level)
        _mix(weight, _sin(len(weight), 310, 0.018 * level))
        _env_exp(weight, 1.0, 0.0, 7.0)
        _m4_fade(weight, 0.009, 0.05)
        _offset_mix(buf, weight, int(SAMPLE_RATE * (start + 0.04)))
    return _wav(_match_peak(_m4_fade(buf, 0.012, 0.045), 0.26))


def _gen_m4_crowd():
    """Distant overlapping cheer swells and murmur, without articulated voices."""
    rng = random.Random(7403)
    n = int(SAMPLE_RATE * 5.0)
    buf = _m4_noise(n, rng, 110, 900, 0.045)
    _mix(buf, _m4_noise(n, rng, 750, 1800, 0.016))
    for _ in range(16):
        dur = rng.uniform(0.65, 1.45)
        length = int(SAMPLE_RATE * dur)
        cheer = _m4_noise(length, rng, rng.uniform(220, 420),
                          rng.uniform(1050, 1550), rng.uniform(0.021, 0.038))
        rate = rng.uniform(0.6, 1.3)
        phase = rng.uniform(0.0, 2.0 * math.pi)
        for i in range(length):
            cheer[i] = int(cheer[i] * (0.75 + 0.25 * math.sin(
                2.0 * math.pi * rate * i / SAMPLE_RATE + phase)))
        _m4_fade(cheer, dur * 0.30, dur * 0.45)
        _offset_mix(buf, cheer, int(SAMPLE_RATE * rng.uniform(0.15, 3.5)))
    _lp(buf, 1600, 2)
    return _wav(_match_peak(_m4_fade(buf, 0.45, 1.2), 0.12))


def _gen_m4_aftermath():
    """Sparse unresolved low chord, gently receding rather than resolving."""
    n = int(SAMPLE_RATE * 5.0)
    buf = _arr(n)
    for idx, (freq, amp, start) in enumerate(((55.0, 0.060, 0.0),
                                             (82.41, 0.028, 0.28),
                                             (116.54, 0.023, 0.75))):
        offset = int(SAMPLE_RATE * start)
        voice = _harmonics(n - offset, freq, [1.0, 0.22, 0.07], amp)
        _m4_fade(voice, 0.75 + idx * 0.2, 2.6)
        _offset_mix(buf, voice, offset)
    _env_exp(buf, 1.0, 0.0, 1.3)
    return _wav(_match_peak(_m4_fade(buf, 0.65, 3.8), 0.14))


def _gen_m4_roof_air():
    """Pre-shaped quiet rooftop air, with a continuous eight-second loop."""
    rng = random.Random(7405)
    n = int(SAMPLE_RATE * 8.0)
    # Folding removes the extra overlap, preserving the exact loop duration.
    length = n + int(SAMPLE_RATE * 0.4)
    buf = _m4_noise(length, rng, 75, 1400, 0.055)
    _mix(buf, _m4_noise(length, rng, 35, 220, 0.012))
    buf = _seamless_loop(buf, ms=400)
    # Warm the final filter from the loop's own tail, not a silent initial state.
    warmup = int(SAMPLE_RATE * 0.1)
    buf = buf[-warmup:] + buf
    _lp(buf, 900, 2)
    buf = buf[warmup:]
    for i in range(n):
        phase = 2.0 * math.pi * i / n
        gain = 0.88 + 0.08 * math.sin(phase + 0.4) + 0.04 * math.sin(2.0 * phase + 1.2)
        buf[i] = int(buf[i] * gain)
    return _wav(_match_peak(buf, 0.045))


def _gen_m4_breath():
    """A single soft, warm breath-noise swell, with no pitched vocalization."""
    rng = random.Random(7406)
    n = int(SAMPLE_RATE * 1.0)
    buf = _m4_noise(n, rng, 160, 1500, 0.11)
    _mix(buf, _m4_noise(n, rng, 900, 2500, 0.02))
    _lp(buf, 1800, 1)
    for i in range(n):
        x = i / (n - 1)
        swell = math.sin(math.pi * x) ** 1.8 * math.exp(-0.65 * x)
        flutter = 0.90 + 0.10 * math.sin(2.0 * math.pi * 2.4 * i / SAMPLE_RATE + 0.3)
        buf[i] = int(buf[i] * swell * flutter)
    return _wav(_match_peak(_m4_fade(buf, 0.07, 0.18), 0.085))


LAZY_GENS = [
    ("footstep_metal_1", _gen_footstep_metal),
    ("footstep_metal_2", _gen_footstep_metal_b),
    ("footstep_metal_3", _gen_footstep_metal_c),
    ("footstep_grate_1", _gen_footstep_grate),
    ("footstep_grate_2", _gen_footstep_grate_b),
    ("footstep_wet_1", _gen_footstep_wet),
    ("footstep_wet_2", _gen_footstep_wet_b),
    ("footstep_water_1", _gen_footstep_water),
    ("footstep_water_2", _gen_footstep_water_b),
    ("footstep_debris_1", _gen_footstep_debris),
    ("footstep_debris_2", _gen_footstep_debris_b),
    ("enemy_footstep_1", _gen_enemy_footstep),
    ("enemy_footstep_2", _gen_enemy_footstep_b),
    ("enemy_footstep_3", _gen_enemy_footstep_c),
    ("volkov_step", _gen_volkov_step),
    ("detainee_shuffle", _gen_detainee_shuffle),
    ("boot_step_tile", _gen_boot_step_tile),
    ("chair_drag", _gen_chair_drag),
    ("chair_scrape_short", _gen_chair_scrape_short),
    ("room_tone", _gen_room_tone),
    ("elec_hum", _gen_elec_hum),
    ("rain_inside", _gen_rain_inside),
    ("wind_gust", _gen_wind_gust),
    ("drip_echo", _gen_drip_echo),
    ("pa_chime", _gen_pa_chime),
    ("pa_mumble", _gen_pa_mumble),
    ("debris_settle", _gen_debris_settle),
    ("m4_tension", _gen_m4_tension),
    ("m4_cuff_close", _gen_m4_cuff_close),
    ("m4_crowd", _gen_m4_crowd),
    ("m4_aftermath", _gen_m4_aftermath),
    ("m4_roof_air", _gen_m4_roof_air),
    ("m4_breath", _gen_m4_breath),
]

def _gen_melee_hit():
    """Flesh impact (v2): a band-limited slap transient, a dark wet body and a
    pitch-dropping impact thud, with a little irregular crackle. The old version
    layered a pure-sine harmonic stack and an FM metallic ring, which read as a
    synth hit - harmonic stacks are exactly what flesh is NOT."""
    n = int(SAMPLE_RATE * 0.22)
    buf = _arr(n)

    # 1. contact: very short broadband slap, mids-forward (the "thwack")
    slap_n = int(SAMPLE_RATE * 0.013)
    slap = _pink(slap_n, 1.0)
    _bp(slap, 420, 2900)
    _env_exp(slap, 1.0, 0.001, 130.0)
    _mix(buf, slap, 0.90)

    # 2. wet body: dark and short, no tonal content at all
    body = _pink(n, 0.80)
    _lp(body, 430, 2)
    _env_exp(body, 1.0, 0.001, 21.0)
    _mix(buf, body, 0.62)

    # 3. mass transfer: pitch-dropping thud (a struck body moves)
    thud = _sine_sweep(n, 122, 48, 0.66)
    _env_exp(thud, 1.0, 0.001, 13.0)
    _mix(buf, thud, 0.72)

    # 4. irregular bone/skin crackle a few ms in - organic, not a tuned ring
    cr = _crackle(int(SAMPLE_RATE * 0.055), 0.38, 0.30, 700, 3200)
    _offset_mix(buf, cr, int(SAMPLE_RATE * 0.006))

    _soft_clip(buf, 1.40)
    return _wav(_match_rms(buf, -17.2))


def _gen_bullet_impact():
    """Concrete ricochet: hard punch, debris lowpass hiss, and dual FM metallic whine."""
    n = int(SAMPLE_RATE * 0.08)
    buf = _arr(n)
    
    # Hard transient
    tick_n = int(SAMPLE_RATE * 0.0015)
    tick = _noise(tick_n, 0.9)
    _mix(buf, tick)
    
    # Impact body
    body = _noise(n, 0.48)
    _resonant_filter(body, 650, 0.4, "low")
    _env_exp(body, 1.0, 0.001, 35.0)
    _mix(buf, body)
    
    # Ricochet whine (FM sine sweep: gorgeous laser-ricochet ring!)
    whine_n = int(SAMPLE_RATE * 0.035)
    whine = _fm(whine_n, 2100, 0.22, 4200, 3.2, decay_rate=25.0)
    _env_exp(whine, 1.0, 0.001, 40.0)
    _offset_mix(buf, whine, int(SAMPLE_RATE * 0.002))
    
    _soft_clip(buf, 1.25)
    return _wav(buf)

def _gen_bullet_impact_enemy():
    """Flesh bullet hit: squishy wet splatter + chest-pounding FM low thump."""
    n = int(SAMPLE_RATE * 0.10)
    buf = _arr(n)
    
    # Squishy wet splatter (noise, heavily lowpassed with high resonance Q)
    wet = _noise(n, 0.52)
    _resonant_filter(wet, 180, 0.65, "low")
    _env_exp(wet, 1.0, 0.001, 16.0)
    _mix(buf, wet)
    
    # Low chest thump (FM)
    thump = _fm(n, 58, 0.6, 116, 1.5, decay_rate=12.0)
    _env_exp(thump, 1.0, 0.001, 14.0)
    _mix(buf, thump)
    
    # Upper bone crack
    crack_n = int(SAMPLE_RATE * 0.0025)
    crack = _noise(crack_n, 0.55)
    _env_exp(crack, 1.0, 0.001, 70.0)
    _offset_mix(buf, crack, 0)
    
    _soft_clip(buf, 1.4)
    return _wav(buf)

def _gen_door_creak():
    """Wooden friction creak: slow pitch FM modulator sweep + resonant low groan."""
    n = int(SAMPLE_RATE * 0.6)
    buf = _arr(n)
    
    # Swept FM friction squeak
    squeak = _fm(n, 340, 0.28, 48, 1.8)
    for i in range(n):
        t = i / n
        pitch_mod = 1.0 + 0.55 * math.sin(t * math.pi * 3.5)
        squeak[i] = int(squeak[i] * pitch_mod)
    _env_adsr(squeak, 0.12, 0.28, 0.45, 0.15, 0.5)
    
    # Wood body groan noise (bandpassed)
    groan = _noise(n, 0.24)
    _resonant_filter(groan, 220, 0.65, "low")
    _env_exp(groan, 1.0, 0.001, 4.0)
    
    _mix(buf, squeak)
    _mix(buf, groan)
    _apply_delay(buf, 40, feedback=0.25, wet=0.2)
    _soft_clip(buf, 1.25)
    return _wav(buf)

def _gen_door_rattle():
    """Heavy steel door punched (v2): structural thud plus a real sheet-steel
    rattle built from inharmonic plate modes and buzzing noise grains across
    several decaying impacts. The old version used a single 2-op FM partial pair
    at a non-integer ratio, which read as a synth zap rather than metal."""
    n = int(SAMPLE_RATE * 0.42)
    buf = _arr(n)

    # The punch itself: dark mass movement
    thud = _brown(n, 0.60)
    _lp(thud, 170, 2)
    _env_exp(thud, 1.0, 0.001, 17.0)
    _mix(buf, thud)
    sub = _sine_sweep(n, 64, 33, 0.52)
    _env_exp(sub, 1.0, 0.001, 11.0)
    _mix(buf, sub)

    # Steel plate: clamped-plate mode ratios (1, 2.71, 5.06, 7.8, 10.9) are
    # strongly inharmonic - that inharmonicity is what sounds like metal.
    plate_modes = [(1.0, 1.0), (2.71, 0.50), (5.06, 0.28), (7.80, 0.15), (10.9, 0.07)]
    for k, (dt, g) in enumerate(((0.006, 1.00), (0.048, 0.52), (0.101, 0.36),
                                 (0.158, 0.22), (0.217, 0.12))):
        off = int(SAMPLE_RATE * dt)
        m = min(int(SAMPLE_RATE * 0.15), n - off)
        if m <= 32:
            continue
        p = _plate(m, 336.0 * (1.0 + 0.05 * k), plate_modes, 0.40 * g, decay=27.0 + 7.0 * k)
        _offset_mix(buf, p, off)
        # plate buzz between the ringing modes
        bz = _crackle(min(int(SAMPLE_RATE * 0.05), n - off), 0.55, 0.30 * g, 1500, 5600)
        _offset_mix(buf, bz, off)

    _lp(buf, 7200, 1)
    _soft_clip(buf, 1.30)
    return _wav(_match_rms(buf, -18.7))


def _gen_door_open():
    """Deadbolt mechanics: crisp latch snap + metal handle friction sweep."""
    n = int(SAMPLE_RATE * 0.3)
    buf = _arr(n)
    
    slide = _fm(n, 180, 0.32, 540, 3.0, decay_rate=8.0)
    _env_exp(slide, 1.0, 0.001, 8.0)
    _mix(buf, slide)
    
    # High crisp metal snap (FM operator)
    click_n = int(SAMPLE_RATE * 0.02)
    click = _fm(click_n, 3200, 0.55, 4800, 4.5, decay_rate=35.0)
    _env_exp(click, 1.0, 0.001, 40.0)
    _offset_mix(buf, click, 0)
    
    _soft_clip(buf, 1.2)
    return _wav(buf)

def _gen_reload():
    """Tactical reload (v2): mag out -> mag in -> slide release, built from
    inharmonic metal plate resonances, friction noise bands, a dropped mag and
    irregular micro-impacts. The old version was three pure FM tones at exact
    offsets, which is why it read as robotic rather than mechanical."""
    n = int(SAMPLE_RATE * 0.60)
    buf = _arr(n)

    def click(t, lo, hi, gain, dec):
        L = int(SAMPLE_RATE * t)
        c = _pink(L, gain)
        _bp(c, lo, hi)
        _env_exp(c, 1.0, 0.001, dec)
        # a sub-millisecond attack ramp. An infinitely sharp click drives the
        # crest factor so high that the peak guard pulls the whole sound down.
        r = max(2, int(SAMPLE_RATE * 0.0009))
        for i in range(min(r, L)):
            c[i] = int(c[i] * (i / float(r)))
        return c

    def plate(t, f0, modes, gain, dec, at):
        L = min(int(SAMPLE_RATE * t), n - at)
        if L <= 32:
            return
        _offset_mix(buf, _plate(L, f0, modes, gain, decay=dec), at)

    # --- stage 1 (t=0.03): mag release button, then the mag sliding out
    _offset_mix(buf, click(0.010, 1600, 6200, 0.30, 120.0), int(SAMPLE_RATE * 0.030))
    plate(0.10, 780.0, [(1.0, 1.0), (2.41, 0.40), (4.10, 0.18)], 0.22, 26.0,
          int(SAMPLE_RATE * 0.033))
    s1 = _pink(int(SAMPLE_RATE * 0.075), 0.30)
    _bp(s1, 900, 3600)
    _env_adsr(s1, 0.16, 0.30, 0.60, 0.32, 0.50)
    _offset_mix(buf, s1, int(SAMPLE_RATE * 0.048))

    # --- the empty mag hits the floor (t=0.17) - a real reload has this beat
    fl = _pink(int(SAMPLE_RATE * 0.055), 0.52)
    _bp(fl, 280, 2600)
    _env_exp(fl, 1.0, 0.001, 52.0)
    _offset_mix(buf, fl, int(SAMPLE_RATE * 0.170), 0.55)
    plate(0.09, 420.0, [(1.0, 1.0), (1.93, 0.42), (3.4, 0.17)], 0.14, 22.0,
          int(SAMPLE_RATE * 0.172))

    # --- stage 2 (t=0.28): fresh mag slapped in - deeper and heavier
    _offset_mix(buf, click(0.009, 700, 4100, 0.30, 130.0), int(SAMPLE_RATE * 0.280))
    plate(0.16, 302.0, [(1.0, 1.0), (1.87, 0.55), (3.02, 0.30), (4.70, 0.15)], 0.34, 16.0,
          int(SAMPLE_RATE * 0.282))
    th = _brown(int(SAMPLE_RATE * 0.12), 0.30)
    _lp(th, 230, 2)
    _env_exp(th, 1.0, 0.001, 30.0)
    _offset_mix(buf, th, int(SAMPLE_RATE * 0.280))

    # --- stage 3 (t=0.46): slide travels back, then snaps forward
    for t0, g, lo, hi in ((0.425, 0.20, 1700, 6800), (0.495, 0.15, 2000, 7600)):
        sf = _pink(int(SAMPLE_RATE * 0.050), g)
        _bp(sf, lo, hi)
        _env_adsr(sf, 0.20, 0.30, 0.50, 0.32, 0.50)
        _offset_mix(buf, sf, int(SAMPLE_RATE * t0))
    _offset_mix(buf, click(0.007, 2500, 7600, 0.26, 165.0), int(SAMPLE_RATE * 0.470))
    plate(0.13, 1180.0, [(1.0, 1.0), (2.63, 0.38), (5.20, 0.16)], 0.20, 32.0,
          int(SAMPLE_RATE * 0.472))

    # handling noise throughout - a real reload is never silent between
    # stages. This also lowers the crest factor: sharp clicks alone cannot
    # reach the original RMS without the peak guard clamping them down.
    _mix(buf, _crackle(n, 0.17, 0.30, 900, 4200), 0.95)
    hands = _pink(n, 0.34)
    _bp(hands, 340, 2600)
    _env_adsr(hands, 0.08, 0.22, 0.78, 0.26, 0.80)
    _mix(buf, hands, 1.0)

    _lp(buf, 9200, 1)
    _soft_clip(buf, 1.25)
    return _wav(_match_rms(buf, -16.5))


def _gen_ambient_drone():
    """Deep industrial machine hum: Tri-operator FM drone with perfect 5th harmonics + LFO swept resonant lowpass filter."""
    dur = 4.0
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    # Stacking FM drone operators (sub, mid, fifth)
    drone1 = _fm(n, 55, 0.30, 11, 2.0)
    drone2 = _fm(n, 82.5, 0.18, 16.5, 1.5)  # Perfect fifth
    drone3 = _fm(n, 110, 0.12, 5.5, 1.0)
    _mix(buf, drone1)
    _mix(buf, drone2)
    _mix(buf, drone3)
    
    # Moving resonant lowpass filter on noise bed (Slow sweep over 4 seconds)
    noise = _noise(n, 0.14)
    out_noise = _arr(n)
    low = 0.0
    band = 0.0
    for i in range(n):
        # LFO modulating cutoff from 130Hz to 230Hz
        cutoff = 180.0 + 50.0 * math.sin(i * 0.0003)
        f = 2.0 * math.sin(math.pi * cutoff / SAMPLE_RATE)
        high = float(noise[i]) - low - 0.45 * band
        band += f * high
        low += f * band
        out_noise[i] = int(max(-MAX_AMP, min(MAX_AMP, band)))
    _mix(buf, out_noise)
    
    # Soft global loop boundaries fade
    fade = int(n * 0.05)
    for i in range(fade):
        t = i / fade
        buf[i] = int(buf[i] * t)
        buf[n - 1 - i] = int(buf[n - 1 - i] * t)
        
    _soft_clip(buf, 1.1)
    return _wav(buf)

def _gen_rain():
    """Rain (v2): a pink-noise rainfall bed shaped by smooth non-resonant
    filtering, slow level movement for gusting, irregular non-ringing droplet
    grains, and a distant low rumble so it is not all treble. The old version
    was white noise with droplets through a high-Q resonant peak at 2.2 kHz -
    exactly the Geiger-counter "radiation" quality that was reported."""
    dur = 3.0
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)

    bed = _pink(n, 0.46)
    _lp(bed, 1650, 3)                # dark and steady; the original sat ~450 Hz
    _hp(bed, 170, 1)
    # slow gusting so the bed is alive rather than a flat hiss
    for i in range(n):
        t = i / float(SAMPLE_RATE)
        g = 0.85 + 0.15 * math.sin(2.0 * math.pi * 0.23 * t) * math.sin(2.0 * math.pi * 0.071 * t + 1.1)
        bed[i] = int(bed[i] * g)
    _mix(buf, bed)

    # droplets: randomised short noise grains with NO resonant filter, so they
    # splash instead of ringing
    for _ in range(64):
        L = int(SAMPLE_RATE * _rnd(0.004, 0.013))
        off = _rng_legacy.randint(0, max(0, n - L))
        d = _pink(L, _rnd(0.13, 0.30))
        _bp(d, _rnd(430, 1500), _rnd(1700, 3000))   # soft splashes, never hissy
        _env_exp(d, 1.0, 0.001, _rnd(60.0, 125.0))
        _offset_mix(buf, d, off)

    # distant rumble body
    rum = _brown(n, 0.12)
    _lp(rum, 130, 2)
    _mix(buf, rum)

    fade = int(n * 0.04)
    for i in range(fade):
        t = i / float(fade)
        buf[i] = int(buf[i] * t)
        buf[n - 1 - i] = int(buf[n - 1 - i] * t)
    return _wav(_match_rms(buf, -30.0))


def _gen_thunder_rumble():
    """Distant thunder for the M5 finale's scripted lightning: a far-off
    crack buried in brown-noise rumble. Lowpassed hard (no near-storm
    snap), slow swell then a long uneven decay. Deterministic through
    LEGACY_RNG like every shared generator (finale_audio reseeds it
    per sound name before calling)."""
    dur = 2.6
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)

    rum = _brown(n, 0.85)
    _lp(rum, 120, 3)
    # two uneven swells, then the long tail
    for i in range(n):
        t = i / float(SAMPLE_RATE)
        g = (min(1.0, t / 0.28) ** 1.5) * math.exp(-t * 1.55) \
            + 0.45 * math.exp(-((t - 0.85) ** 2) / 0.09)
        rum[i] = int(rum[i] * min(1.2, g))
    _mix(buf, rum)

    # the crack itself, muffled by distance
    crack = _pink(int(SAMPLE_RATE * 0.14), 0.30)
    _lp(crack, 420, 2)
    _env_exp(crack, 1.0, 0.001, 90.0)
    _offset_mix(buf, crack, int(SAMPLE_RATE * 0.03))

    fade = int(SAMPLE_RATE * 0.01)
    for i in range(fade):
        t = i / float(fade)
        buf[i] = int(buf[i] * t)
    return _wav(_match_rms(buf, -27.0))


def _gen_wind():
    """Swirling storm gusts: slow swept resonant filter on wind noise + sub bass rumble."""
    dur = 4.0
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    noise = _noise(n, 0.15)
    # Slow LFO frequency sweep to emulate rushing wind gusts
    low = 0.0
    band = 0.0
    q = 0.32
    for i in range(n):
        t = i / SAMPLE_RATE
        cutoff = 380.0 + 160.0 * math.sin(t * 0.8) + 60.0 * math.cos(t * 1.6)
        f = 2.0 * math.sin(math.pi * cutoff / SAMPLE_RATE)
        high = float(noise[i]) - low - q * band
        band += f * high
        low += f * band
        buf[i] = int(max(-MAX_AMP, min(MAX_AMP, low)))
        
    # Deep physical sub roar (modulated volume)
    sub = _sin(n, 42, 0.06)
    for i in range(n):
        t = i / SAMPLE_RATE
        sub[i] = int(sub[i] * (0.35 + 0.65 * math.sin(t * 0.5)))
    _mix(buf, sub)
    
    fade = int(n * 0.05)
    for i in range(fade):
        t = i / fade
        buf[i] = int(buf[i] * t)
        buf[n - 1 - i] = int(buf[n - 1 - i] * t)
        
    _soft_clip(buf, 1.15)
    return _wav(buf)

def _gen_explosion():
    """Muffled devastating explosion: thick resonant low-pass roar + deep FM sub thuds + falling concrete crackles + room space echoes."""
    dur = 1.5
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    # 1. Main rumble
    noise = _noise(n, 0.82)
    _resonant_filter(noise, 220, 0.4, "low")
    _env_adsr(noise, 0.04, 0.28, 0.5, 0.15, 0.7)
    _mix(buf, noise)
    
    # 2. Huge dual FM chest thumps
    thump = _fm(n, 38, 0.8, 76, 1.8, decay_rate=5.0)
    _env_adsr(thump, 0.02, 0.4, 0.5, 0.05, 0.9)
    _mix(buf, thump)
    
    # 3. High-freq cracking debris
    for _ in range(8):
        off = _rng_legacy.randint(0, int(SAMPLE_RATE * 0.3))
        ln = int(SAMPLE_RATE * 0.08)
        crack = _noise(ln, 0.35)
        _resonant_filter(crack, 1500, 0.3)
        _env_exp(crack, 1.0, 0.001, 15.0)
        _offset_mix(buf, crack, off)
        
    # Global delay echo
    _apply_delay(buf, 180, feedback=0.45, wet=0.35)
    _apply_delay(buf, 75, feedback=0.25, wet=0.2)
    
    _soft_clip(buf, 1.5)
    _env_exp(buf, 1.0, 0.001, 2.5)
    return _wav(buf)

def _gen_heartbeat():
    """Deep chest pulse: dual-thump FM sweep for heavy pressure wave."""
    dur = 1.8
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    beat_n = int(SAMPLE_RATE * 0.16)
    
    for offset in [int(SAMPLE_RATE * 0.1), int(SAMPLE_RATE * 0.42)]:
        # Dual-thump FM: carrier 45Hz modulated by 22Hz (very heavy sub bass)
        beat = _fm(beat_n, 45, 0.72, 22, 1.2, decay_rate=14.0)
        _env_exp(beat, 1.0, 0.001, 10.0)
        _offset_mix(buf, beat, offset)
        
    floor = _noise(n, 0.01)
    _mix(buf, floor)
    
    fade = int(n * 0.02)
    for i in range(fade):
        t = i / fade
        buf[i] = int(buf[i] * t)
        buf[n - 1 - i] = int(buf[n - 1 - i] * t)
    return _wav(buf)

def _gen_menu_click():
    """Crisp elegant 16-bit chime click: quick high-quality FM metal tap."""
    n = int(SAMPLE_RATE * 0.025)
    buf = _arr(n)
    
    click = _fm(n, 1500, 0.48, 2200, 3.5, decay_rate=45.0)
    _env_exp(click, 1.0, 0.001, 55.0)
    _mix(buf, click)
    
    body = _sin(n, 440, 0.22)
    _env_exp(body, 1.0, 0.001, 35.0)
    _mix(buf, body)
    
    _soft_clip(buf, 1.1)
    return _wav(buf)

def _gen_menu_hover():
    """Very subtle high-frequency FM blip."""
    n = int(SAMPLE_RATE * 0.008)
    buf = _arr(n)
    click = _fm(n, 2800, 0.26, 4200, 1.5, decay_rate=75.0)
    _env_exp(click, 1.0, 0.001, 80.0)
    _mix(buf, click)
    return _wav(buf)

def _gen_radio_static():
    """Handset static (v2): pink noise band-limited to a small speaker's
    passband, with a slow amplitude irregularity so it breathes, an impulsive
    crackle layer, and a few louder squelch bursts. The old version was white
    noise through high-Q resonant bursts, which read as Geiger-counter
    "radiation" rather than a radio."""
    dur = 1.5
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)

    # speaker hiss floor - pink, and hard band-limited like a handset
    hiss = _pink(n, 0.34)
    _bp(hiss, 400, 2600)
    _lp(hiss, 2500, 3)               # nothing above a small speaker can pass
    for i in range(n):
        t = i / float(SAMPLE_RATE)
        g = 0.74 + 0.26 * math.sin(2.0 * math.pi * 1.7 * t + 0.6)
        buf[i] = int(hiss[i] * g)

    # impulsive crackle on top of the hiss
    _mix(buf, _crackle(n, 0.10, 0.50, 600, 2400))

    # squelch bursts - the "gate opening" feel of a real handset
    for _ in range(6):
        L = int(SAMPLE_RATE * _rnd(0.030, 0.085))
        off = _rng_legacy.randint(0, max(0, n - L))
        b = _pink(L, 0.62)
        _bp(b, 480, 2350)
        _lp(b, 2300, 2)
        _env_adsr(b, 0.10, 0.20, 0.70, 0.35, 0.60)
        _offset_mix(buf, b, off, _rnd(0.25, 0.50))

    _hp(buf, 320, 2)
    _lp(buf, 2800, 3)
    fade = int(n * 0.03)
    for i in range(fade):
        t = i / float(fade)
        buf[i] = int(buf[i] * t)
        buf[n - 1 - i] = int(buf[n - 1 - i] * t)
    return _wav(_match_rms(buf, -38.9))


def _gen_radio_chatter():
    """Garbled vocal transmission: ring modulator + swept bandpass on noise (classic military radio speaker feel)."""
    dur = 2.0
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    noise = _noise(n, 0.22)
    # Garble with Ring Modulation (multiplied by a 400Hz voice pitch)
    for i in range(n):
        mod = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * 380 * i / SAMPLE_RATE))
        buf[i] = int(noise[i] * mod)
        
    # Bandpass voice filter to isolate nasal speaking frequencies
    _resonant_filter(buf, 950, 0.6, "band")
    _env_adsr(buf, 0.08, 0.18, 0.5, 0.2, 0.5)
    
    # Intermittent squelch bursts
    for _ in range(8):
        burst_start = _rng_legacy.randint(0, n - int(SAMPLE_RATE * 0.02))
        burst = _noise(int(SAMPLE_RATE * 0.015), 0.32)
        _resonant_filter(burst, 3500, 0.3, "high")
        _env_exp(burst, 1.0, 0.001, 40.0)
        _offset_mix(buf, burst, burst_start)
        
    _soft_clip(buf, 1.35)
    return _wav(buf)

def _gen_water_drip():
    """Cavern drip (v2): a bubble "plink" with a fast rising pitch plus a tiny
    surface-noise burst, followed by a long dark multi-tap cavern echo that
    loses treble with distance. The old version used a 35 ms feedback delay,
    which is a flutter echo - it reads as a small box, not a cave."""
    n = int(SAMPLE_RATE * 1.60)
    buf = _arr(n)

    # impact transient
    imp = int(SAMPLE_RATE * 0.004)
    a = _pink(imp, 0.95)
    _bp(a, 1200, 6200)
    _env_exp(a, 1.0, 0.001, 230.0)
    _offset_mix(buf, a, 0)

    # the bubble: fast rising pitch, short and damped - the signature "plink"
    bub = int(SAMPLE_RATE * 0.055)
    t1 = _sine_sweep(bub, 470, 1420, 0.44)
    _env_exp(t1, 1.0, 0.001, 27.0)
    _offset_mix(buf, t1, 0)

    # water body around the impact
    w = _pink(int(SAMPLE_RATE * 0.050), 0.24)
    _bp(w, 380, 2600)
    _env_exp(w, 1.0, 0.001, 42.0)
    _offset_mix(buf, w, int(SAMPLE_RATE * 0.002))

    # cavern: long, irregular, darkening taps. Weighted to the early
    # reflections so the space reads clearly instead of a faint wash.
    _multitap(buf, [118, 236, 372, 528, 706, 912],
              [0.52, 0.40, 0.30, 0.20, 0.13, 0.08], wet=0.85)
    _lp(buf, 2600, 2)                # rock absorbs treble over distance
    return _wav(_match_peak(buf, 0.315))


def _gen_mission_complete():
    """Mission resolved (v2): a warm sustained major chord of soft-attack,
    slightly detuned harmonic voices with a long natural release and a low pad.
    Replaces the FM-brass arpeggio, which read as an 8-bit fanfare."""
    dur = 2.2
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)

    chord = [196.0, 261.6, 329.6, 392.0, 523.3]      # G3 C4 E4 G4 C5
    note = int(SAMPLE_RATE * 1.7)
    for idx, f in enumerate(chord):
        start = int(SAMPLE_RATE * 0.10 * idx)         # gentle stagger, not a fast arp
        for det in (-0.0024, 0.0024):                 # two detuned voices = chorus
            v = _harmonics(note, f * (1.0 + det), [1.0, 0.30, 0.09, 0.03], 0.17)
            _env_adsr(v, 0.34, 0.18, 0.72, 0.52, 0.80)   # slow attack, long release
            _lp(v, 4200, 2)
            _offset_mix(buf, v, start)

    # low pad for weight, so it is not all treble shimmer
    pad = _harmonics(n, 98.0, [1.0, 0.35, 0.12], 0.20)
    _env_adsr(pad, 0.30, 0.20, 0.80, 0.48, 0.85)
    _lp(pad, 900, 2)
    _mix(buf, pad, 0.85)

    _multitap(buf, [125, 255, 400], [0.26, 0.17, 0.10], wet=0.45)
    _soft_clip(buf, 1.12)
    return _wav(_match_rms(buf, -14.7))


def _gen_breach():
    """Wall breaching explosion: heavy plaster/wooden door splintering crash, massive low rumble, no sci-fi beeps."""
    dur = 0.85
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    # 1. Main splintering/crushing noise
    noise = _noise(n, 0.8)
    _resonant_filter(noise, 340, 0.45, "low")
    _env_adsr(noise, 0.01, 0.22, 0.48, 0.25, 0.6)
    _mix(buf, noise)
    
    # 2. Massive low-frequency structural thump (FM sub thud)
    thump = _fm(n, 75, 0.72, 38, 1.5, decay_rate=12.0)
    _env_adsr(thump, 0.0, 0.18, 0.5, 0.32, 0.7)
    _mix(buf, thump)
    
    # 3. Falling plaster and wooden debris crumble (noise swept from high-mid to low)
    debris_n = int(SAMPLE_RATE * 0.45)
    debris = _noise(debris_n, 0.52)
    low = 0.0
    band = 0.0
    q = 0.35
    for i in range(debris_n):
        t = i / debris_n
        cutoff = 1800.0 - 1500.0 * (t ** 0.5) # sweep down from 1800Hz to 300Hz
        f = 2.0 * math.sin(math.pi * cutoff / SAMPLE_RATE)
        high = float(debris[i]) - low - q * band
        band += f * high
        low += f * band
        debris[i] = int(max(-MAX_AMP, min(MAX_AMP, band)))
    _env_exp(debris, 1.0, 0.001, 8.0)
    _offset_mix(buf, debris, int(SAMPLE_RATE * 0.01))
    
    _apply_delay(buf, 90, feedback=0.4, wet=0.28)
    _soft_clip(buf, 1.45)
    return _wav(buf)

def _gen_molotov_throw():
    """Whoosh of a burning rag bottle being thrown: soft attack, sweeping wind-like noise."""
    dur = 0.35
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    # Whoosh noise swept from low-mid
    noise = _noise(n, 0.45)
    low = 0.0
    band = 0.0
    q = 0.25
    for i in range(n):
        t = i / n
        cutoff = 180.0 + 320.0 * math.sin(t * math.pi)
        f = 2.0 * math.sin(math.pi * cutoff / SAMPLE_RATE)
        high = float(noise[i]) - low - q * band
        band += f * high
        low += f * band
        buf[i] = int(max(-MAX_AMP, min(MAX_AMP, low)))
        
    _env_adsr(buf, 0.12, 0.18, 0.6, 0.1, 0.7)
    _soft_clip(buf, 1.25)
    return _wav(buf)

def _gen_molotov_explode():
    """Molotov ignition burst: sharp bottle smash + roaring liquid fire burst."""
    dur = 1.3
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    # 1. Glass bottle smash (scattered high-pitch FM ringing)
    for _ in range(6):
        shard_start = _rng_legacy.randint(0, int(SAMPLE_RATE * 0.04))
        shard_len = int(SAMPLE_RATE * 0.05 + _rng_legacy.random() * 0.05)
        freq = 3400 + _rng_legacy.random() * 2500
        shard = _fm(shard_len, freq, 0.35, freq * 1.4, 3.5, decay_rate=22.0)
        _env_exp(shard, 1.0, 0.001, 35.0)
        _offset_mix(buf, shard, shard_start)
        
    # 2. Liquid fire burst whoosh (noise swept via resonant bandpass filter)
    whoosh_n = int(SAMPLE_RATE * 0.8)
    whoosh = _noise(whoosh_n, 0.65)
    low = 0.0
    band = 0.0
    q = 0.45 # high resonance
    for i in range(whoosh_n):
        t = i / whoosh_n
        cutoff = 220.0 + 440.0 * math.sin(t * math.pi)
        f = 2.0 * math.sin(math.pi * cutoff / SAMPLE_RATE)
        high = float(whoosh[i]) - low - q * band
        band += f * high
        low += f * band
        whoosh[i] = int(max(-MAX_AMP, min(MAX_AMP, band)))
        
    _env_adsr(whoosh, 0.02, 0.15, 0.6, 0.25, 0.7)
    _offset_mix(buf, whoosh, int(SAMPLE_RATE * 0.005))
    
    # 3. Flame crackles (high frequency noise spikes)
    for _ in range(15):
        off = _rng_legacy.randint(int(SAMPLE_RATE * 0.05), int(SAMPLE_RATE * 0.65))
        crackle = _noise(int(SAMPLE_RATE * 0.015), 0.28)
        _resonant_filter(crackle, 3500, 0.3, "high")
        _env_exp(crackle, 1.0, 0.001, 60.0)
        _offset_mix(buf, crackle, off)
        
    _apply_delay(buf, 65, feedback=0.25, wet=0.18)
    _soft_clip(buf, 1.35)
    _env_exp(buf, 1.0, 0.001, 2.2)
    return _wav(buf)

def _gen_pickup():
    """Item picked up (v2): a small physical object being handled - a soft
    composite knock, a short inharmonic body resonance, then a lighter second
    tap as confirmation. Replaces the FM/sine "laser sweep", which was the most
    literally arcade sound in the set."""
    n = int(SAMPLE_RATE * 0.26)
    buf = _arr(n)

    # contact knock
    k1 = int(SAMPLE_RATE * 0.010)
    a = _pink(k1, 1.0)
    _bp(a, 850, 5200)
    _env_exp(a, 1.0, 0.001, 115.0)
    _offset_mix(buf, a, 0)
    # body resonance: inharmonic, so it reads as a real object
    b = _plate(int(SAMPLE_RATE * 0.14), 515.0,
               [(1.0, 1.0), (2.13, 0.44), (3.41, 0.21), (5.02, 0.10)], 0.34, decay=20.0)
    _offset_mix(buf, b, int(SAMPLE_RATE * 0.004))

    # second, lighter, higher tap = the "confirm"
    k2 = int(SAMPLE_RATE * 0.008)
    c = _pink(k2, 0.95)
    _bp(c, 1550, 7000)
    _env_exp(c, 1.0, 0.001, 135.0)
    _offset_mix(buf, c, int(SAMPLE_RATE * 0.078))
    d = _plate(int(SAMPLE_RATE * 0.11), 872.0,
               [(1.0, 1.0), (2.31, 0.37), (3.70, 0.15)], 0.20, decay=24.0)
    _offset_mix(buf, d, int(SAMPLE_RATE * 0.081))

    _multitap(buf, [62, 138], [0.16, 0.09], wet=0.30)
    _soft_clip(buf, 1.15)
    return _wav(_match_rms(buf, -24.7))


def _gen_alarm():
    """Industrial security siren (v2): a motor-driven horn.

    Signal order matters here and an earlier attempt got it wrong. A physical
    siren is a tone that a rotor physically INTERRUPTS, so the amplitude chop
    has to be applied AFTER the drive stage - heavy saturation acts as a
    limiter and squashes modulation depth, and a long echo fills the gaps back
    in. Chop last, keep the echo short, and it reads as machinery.

    Replaces a pure sine with vibrato, which was a steady test-tone warble.
    """
    dur = 1.6
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)

    # --- horn voice: slightly inharmonic partial stack, slow mechanical wail
    amps = [1.0, 0.40, 0.24, 0.13, 0.06]
    ratios = [1.0, 2.01, 2.98, 4.04, 5.11]
    tone = _arr(n)
    phases = [_rng_legacy.random() * 2.0 * math.pi for _ in amps]
    for i in range(n):
        t = i / float(SAMPLE_RATE)
        f = 530.0 + 112.0 * math.sin(2.0 * math.pi * 0.55 * t)
        s = 0.0
        for k in range(len(amps)):
            phases[k] += 2.0 * math.pi * f * ratios[k] / SAMPLE_RATE
            s += amps[k] * math.sin(phases[k])
        tone[i] = int(MAX_AMP * 0.26 * s)
    _lp(tone, 3400, 2)               # horn mouth rolloff
    _hp(tone, 180, 1)
    _soft_clip(tone, 2.35)           # driver distortion, BEFORE the chop

    # --- motor and housing noise, also before the chop so it is interrupted too
    motor = _brown(n, 0.26)
    _lp(motor, 300, 2)
    _mix(tone, motor, 0.85)
    _mix(tone, _crackle(n, 0.05, 0.20, 500, 3400), 0.55)

    # --- rotor chop applied LAST: this is the cue that it is a machine.
    # abs(sin(x)) has HALF the period of sin(x), so a 13 Hz argument gates at
    # 26 Hz. Stated explicitly rather than left implicit: an earlier revision
    # documented "13 Hz" while actually chopping at 26 Hz. 26 Hz is the rate we
    # want (13 Hz reads as a slow wobble, 26 Hz as a mechanical interrupter),
    # so ROTOR_HZ is the true gate rate and the argument is halved to match.
    ROTOR_HZ = 26.0
    for i in range(n):
        t = i / float(SAMPLE_RATE)
        g = 0.12 + 0.88 * math.pow(abs(math.sin(math.pi * ROTOR_HZ * t)), 0.35)
        tone[i] = int(tone[i] * g)

    _env_adsr(tone, 0.05, 0.10, 0.85, 0.22, 0.92)
    _mix(buf, tone)

    # short, sparse warehouse taps - a long wash would fill in the chop
    _multitap(buf, [95, 210, 360], [0.30, 0.18, 0.10], wet=0.40)
    _soft_clip(buf, 1.15)
    return _wav(_match_rms(buf, -13.7))



def _gen_empty_click():
    """Pistol dry firing pin: quick dry FM metallic spring snap."""
    n = int(SAMPLE_RATE * 0.03)
    buf = _arr(n)
    
    click = _fm(n, 1800, 0.45, 3400, 5.0, decay_rate=65.0)
    _env_exp(click, 1.0, 0.001, 50.0)
    _mix(buf, click)
    
    return _wav(buf)

def _gen_glass_shatter():
    """Falling glass pane: multiple scattered FM metallic shattering pings + high frequency noise shards."""
    n = int(SAMPLE_RATE * 0.4)
    buf = _arr(n)
    
    # Scattered shard rings
    for _ in range(12):
        shard_start = _rng_legacy.randint(0, n - int(SAMPLE_RATE * 0.05))
        shard_len = int(SAMPLE_RATE * 0.02 + _rng_legacy.random() * 0.03)
        freq = 3100 + _rng_legacy.random() * 4500
        
        # High crisp metallic FM shard ping
        shard = _fm(shard_len, freq, 0.22, freq * 1.5, 4.2, decay_rate=35.0)
        _env_exp(shard, 1.0, 0.001, 40.0)
        
        noise_part = _noise(shard_len, 0.16)
        _resonant_filter(noise_part, 4200, 0.3, "high")
        _env_exp(noise_part, 1.0, 0.001, 50.0)
        
        # Mix shard and noise part
        _mix(shard, noise_part)
        _offset_mix(buf, shard, shard_start)
        
    _soft_clip(buf, 1.2)
    return _wav(buf)

# ── Cinematic procedural sounds ──

def _gen_terminal_glitch():
    """Digital terminal data transfer: rapid FM data chirps and radio packet breakups."""
    rng = random.Random(301)
    dur = 0.34
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    bed = _noise(n, 0.18)
    _resonant_filter(bed, 650, 0.2, "low")
    _env_exp(bed, 1.0, 0.001, 5.0)
    _mix(buf, bed)
    
    # FM digital burst spikes
    for _ in range(11):
        ln = rng.randint(int(SAMPLE_RATE * 0.006), int(SAMPLE_RATE * 0.026))
        off = rng.randint(0, max(1, n - ln))
        
        # Digital data chirp via FM (1800Hz modulated with high index)
        burst = _fm(ln, rng.uniform(1100, 2600), rng.uniform(0.3, 0.55), 3200, 5.0, decay_rate=25.0)
        _env_exp(burst, 1.0, 0.001, rng.uniform(18.0, 45.0))
        _offset_mix(buf, burst, off)
        
    carrier = _sin(n, 95, 0.055)
    _env_exp(carrier, 1.0, 0.001, 3.5)
    _mix(buf, carrier)
    
    _resonant_filter(buf, 1800, 0.1)
    _soft_clip(buf, 1.3)
    _env_linear(buf, 1.0, 0.0)
    return _wav(buf)

def _gen_missile_launch():
    """Rocket motor launch: heavy dirty ignition cough + low engine pressure roar."""
    rng = random.Random(410)
    dur = 0.78
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    # Ignition blast
    cough_n = int(SAMPLE_RATE * 0.12)
    cough = _noise(cough_n, 0.72)
    _resonant_filter(cough, 180, 0.45, "low")
    _env_exp(cough, 1.0, 0.001, 13.0)
    _mix(buf, cough)
    
    # Engine roar (noise, resonant bandpass)
    roar = _noise(n, 0.3)
    _resonant_filter(roar, 140, 0.5, "low")
    for i in range(n):
        wobble = 0.72 + 0.18 * math.sin(i * 0.006) + 0.10 * math.sin(i * 0.019)
        roar[i] = int(roar[i] * wobble)
    _env_adsr(roar, 0.03, 0.20, 0.45, 0.32, 0.48)
    _mix(buf, roar)
    
    # Sub-bass rocket pressure (FM thud)
    sub = _fm(n, 46, 0.3, 23, 0.5, decay_rate=3.0)
    _env_exp(sub, 1.0, 0.001, 3.0)
    _mix(buf, sub)
    
    _apply_delay(buf, 60, feedback=0.3, wet=0.2)
    _soft_clip(buf, 1.4)
    return _wav(buf)

def _gen_missile_flyby():
    """Rushing air doppler effect: swept-cutoff wind roar past listener."""
    dur = 0.92
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    air = _noise(n, 0.36)
    _resonant_filter(air, 450, 0.1, "low")
    
    for i in range(n):
        x = i / n
        whoosh = math.exp(-((x - 0.42) ** 2) / 0.055)
        flutter = 0.86 + 0.14 * math.sin(i * 0.032)
        air[i] = int(air[i] * (0.18 + 1.05 * whoosh) * flutter)
    _mix(buf, air)
    
    low_air = _noise(n, 0.14)
    _resonant_filter(low_air, 120, 0.1, "low")
    _env_adsr(low_air, 0.14, 0.20, 0.38, 0.28, 0.50)
    _mix(buf, low_air)
    
    _env_adsr(buf, 0.10, 0.18, 0.46, 0.26, 0.60)
    _soft_clip(buf, 1.15)
    return _wav(buf)

def _gen_rig_impact_crack():
    """Distant structural collapse crack: giant filtered crunch."""
    dur = 0.55
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    crack_n = int(SAMPLE_RATE * 0.045)
    crack = _noise(crack_n, 0.9)
    _resonant_filter(crack, 380, 0.4, "low")
    _env_exp(crack, 1.0, 0.001, 28.0)
    _mix(buf, crack)
    
    slap = _noise(int(SAMPLE_RATE * 0.20), 0.45)
    _resonant_filter(slap, 180, 0.3)
    _env_exp(slap, 1.0, 0.001, 8.0)
    _offset_mix(buf, slap, int(SAMPLE_RATE * 0.012))
    
    sub = _fm(int(SAMPLE_RATE * 0.36), 52, 0.4, 26, 0.5, decay_rate=5.5)
    _env_exp(sub, 1.0, 0.001, 5.5)
    _offset_mix(buf, sub, int(SAMPLE_RATE * 0.006))
    
    _apply_delay(buf, 140, feedback=0.4, wet=0.3)
    _soft_clip(buf, 1.8)
    return _wav(buf)

def _gen_rig_low_boom():
    """The main dark pressure wave: heavy sub rumble + multi-operator low-end FM."""
    dur = 2.65
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    # Overlapping low FM sub layers
    for off_ms, freq, amp, rate in [(0, 36, 0.62, 2.0), (70, 48, 0.48, 2.4), (160, 68, 0.28, 3.1)]:
        ln = n - int(SAMPLE_RATE * off_ms / 1000)
        tone = _fm(max(1, ln), freq, amp, freq // 2, 0.5, decay_rate=rate)
        _offset_mix(buf, tone, int(SAMPLE_RATE * off_ms / 1000))
        
    rumble = _noise(n, 0.36)
    _resonant_filter(rumble, 80, 0.5, "low")
    for i in range(n):
        rumble[i] = int(rumble[i] * (0.8 + 0.2 * math.sin(i * 0.0017)))
    _env_exp(rumble, 1.0, 0.001, 1.75)
    _mix(buf, rumble)
    
    _apply_delay(buf, 200, feedback=0.35, wet=0.25)
    _soft_clip(buf, 1.35)
    return _wav(buf)

def _gen_rig_secondary_explosion():
    """Muffled fuel tank eruptions: low thuds and deep rumbles."""
    rng = random.Random(512)
    dur = 1.35
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    for start_ms, amp, lp in [(0, 0.48, 120), (130, 0.34, 100), (310, 0.24, 80)]:
        ln = int(SAMPLE_RATE * rng.uniform(0.24, 0.44))
        blast = _noise(ln, amp)
        _resonant_filter(blast, lp, 0.4, "low")
        _env_exp(blast, 1.0, 0.001, rng.uniform(6.0, 9.0))
        _offset_mix(buf, blast, int(SAMPLE_RATE * start_ms / 1000))
        
    sub = _fm(n, 58, 0.22, 29, 0.5, decay_rate=3.4)
    _env_exp(sub, 1.0, 0.001, 3.4)
    _mix(buf, sub)
    
    _apply_delay(buf, 110, feedback=0.3, wet=0.2)
    _soft_clip(buf, 1.4)
    return _wav(buf)

def _gen_rig_metal_collapse():
    """Collapsing metal beams: grinding FM wood/metal groans + heavy thuds."""
    rng = random.Random(777)
    dur = 2.8
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    for off_ms, start_f, end_f, amp in [(0, 130, 72, 0.2), (260, 96, 54, 0.18), (620, 155, 82, 0.12)]:
        ln = n - int(SAMPLE_RATE * off_ms / 1000)
        groan = _sine_sweep(max(1, ln), start_f, end_f, amp)
        grit = _noise(len(groan), amp * 0.9)
        _resonant_filter(grit, 140, 0.6)
        _mix(groan, grit)
        _env_adsr(groan, 0.08, 0.22, 0.48, 0.22, 0.55)
        _offset_mix(buf, groan, int(SAMPLE_RATE * off_ms / 1000))
        
    # Steel frame snap hits
    for _ in range(15):
        off = rng.randint(int(SAMPLE_RATE * 0.18), n - int(SAMPLE_RATE * 0.12))
        ln = rng.randint(int(SAMPLE_RATE * 0.07), int(SAMPLE_RATE * 0.20))
        hit = _noise(ln, rng.uniform(0.14, 0.32))
        _resonant_filter(hit, rng.randint(80, 240), 0.4)
        _env_exp(hit, 1.0, 0.001, rng.uniform(10, 24))
        _offset_mix(buf, hit, off)
        
    _apply_delay(buf, 150, feedback=0.35, wet=0.25)
    _soft_clip(buf, 1.45)
    return _wav(buf)

def _gen_rig_water_splash():
    """Massive ocean splash: low mass surge + steam spray noise."""
    dur = 1.9
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    slap = _noise(int(SAMPLE_RATE * 0.20), 0.58)
    _resonant_filter(slap, 180, 0.3)
    _env_exp(slap, 1.0, 0.001, 10.5)
    _mix(buf, slap)
    
    surge = _noise(n, 0.24)
    _resonant_filter(surge, 90, 0.1, "low")
    _env_exp(surge, 1.0, 0.001, 2.2)
    _mix(buf, surge)
    
    steam = _noise(n, 0.14)
    _resonant_filter(steam, 1100, 0.2)
    _env_adsr(steam, 0.04, 0.26, 0.44, 0.26, 0.52)
    _offset_mix(buf, steam, int(SAMPLE_RATE * 0.11))
    
    wave = _sin(n, 39, 0.12)
    _env_exp(wave, 1.0, 0.001, 2.1)
    _mix(buf, wave)
    
    _apply_delay(buf, 120, feedback=0.3, wet=0.2)
    _soft_clip(buf, 1.25)
    return _wav(buf)

def _gen_rig_fire_burst():
    """Fireball whoosh: dark low whoomp + burning roar crackles."""
    dur = 2.35
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    whoomp = _noise(int(SAMPLE_RATE * 0.62), 0.38)
    _resonant_filter(whoomp, 120, 0.4, "low")
    _env_exp(whoomp, 1.0, 0.001, 4.2)
    _mix(buf, whoomp)
    
    burn = _noise(n, 0.13)
    _resonant_filter(burn, 380, 0.1)
    for i in range(n):
        burn[i] = int(burn[i] * (0.75 + 0.25 * math.sin(i * 0.004)))
    _env_adsr(burn, 0.14, 0.24, 0.44, 0.18, 0.45)
    _mix(buf, burn)
    
    sub = _fm(n, 45, 0.1, 22, 0.3, decay_rate=2.6)
    _env_exp(sub, 1.0, 0.001, 2.6)
    _mix(buf, sub)
    
    _apply_delay(buf, 100, feedback=0.25, wet=0.15)
    _soft_clip(buf, 1.2)
    return _wav(buf)

def _gen_type_tick_variant(freq=1350, amp=0.16, dur=0.042):
    """
    Simulates a highly satisfying mechanical typewriter key strike (tactile mechanical click + hollow platen impact + spring ring).
    """
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    
    # 1. High-frequency tactile switch transient (metal key striking paper/platen)
    snap_n = int(SAMPLE_RATE * 0.005)
    snap = _noise(snap_n, amp * 0.85)
    _resonant_filter(snap, 4500, 0.4, "high")
    _env_exp(snap, 1.0, 0.001, 45.0)
    _mix(buf, snap)
    
    # 2. Hollow mechanical body thud (key mechanism hitting platen roller ~280Hz)
    body = _fm(n, freq * 0.2, amp * 0.45, freq * 0.1, 1.5, decay_rate=18.0)
    _resonant_filter(body, 350, 0.5, "low")
    _env_exp(body, 1.0, 0.001, 25.0)
    _mix(buf, body)
    
    # 3. Tiny ringing steel spring ring (gives it authentic typewriter lever resonance)
    spring = _fm(n, freq * 3.5, amp * 0.28, freq * 4.5, 3.2, decay_rate=30.0)
    _env_exp(spring, 1.0, 0.001, 35.0)
    _mix(buf, spring)
    
    # Apply a tight desk-reflection slapback echo
    _apply_delay(buf, 15, feedback=0.15, wet=0.1)
    
    _soft_clip(buf, 1.2)
    return _wav(buf)

def _gen_type_tick():
    return _gen_type_tick_variant(1320, 0.75, 0.040)

def _gen_type_tick_b():
    return _gen_type_tick_variant(1560, 0.70, 0.038)

def _gen_type_tick_c():
    return _gen_type_tick_variant(1180, 0.72, 0.044)

# ── Trailer overhaul (docs/PLAN_3_AUDIO.md) - ADDITIVE ONLY ──
# New generators use existing primitives above exclusively; every legacy
# _gen_* below renders byte-identically. Registered LAZILY (startup flat).
# 100 BPM @30fps = 18 frames/beat; beat grid = 0.6 s (see TRAILER_BEAT_S).

TRAILER_BPM = 100
TRAILER_BEAT_S = 0.6

def _radio_voice(buf, kind="vasile"):
    """In-game radio treatment matching the trailer VO stem (§2.2/§2.3).

    kind: "vasile" (clean VHF van) | "volkov" (close handheld, hotter) |
    "pa" (diegetic PA horn, large hall). Mutates buf in place, returns it.
    """
    if kind == "volkov":
        _bp(buf, 350, 2200)
    elif kind == "pa":
        _bp(buf, 600, 3200)
    else:
        _bp(buf, 400, 2600)
    _mix(buf, _crackle(len(buf), 0.10, 0.50, 600, 2400), 0.3)
    _soft_clip(buf, 2.0 if kind == "volkov" else 1.5)
    if kind == "pa":
        _multitap(buf, [350, 550], [0.45, 0.35], wet=0.4)
    else:
        _multitap(buf, [60], [0.2], wet=0.2)
    return _guard_peak(buf)

def _gen_squelch_head():
    """30 ms pink burst 480-2350 Hz at -12 dB peak: radio gate opening."""
    L = int(SAMPLE_RATE * 0.030)
    b = _pink(L, 0.50)
    _bp(b, 480, 2350)
    _env_adsr(b, 0.10, 0.20, 0.70, 0.35, 0.60)
    return _wav(_match_peak(b, 0.25))

def _gen_squelch_tail():
    """15 ms highpassed click 3500 Hz at -18 dB peak: radio gate closing."""
    L = int(SAMPLE_RATE * 0.015)
    b = _pink(L, 0.50)
    _hp(b, 3500, 1)
    _env_exp(b, 1.0, 0.001, 90.0)
    return _wav(_match_peak(b, 0.126))

def _gen_riser(dur=8.0):
    """Trailer riser: sine sweep 200->2400 Hz + pink noise lowpass-swept
    300->8000 Hz in 32 chunks + accelerating ticks (8ths->32nds). Swells
    to 0.8 peak (-2 dBTP); caller hard-cuts into the 0:28.4 silence."""
    rng = random.Random(1000 + int(dur * 10))
    _ = rng  # deterministic seed reserved for future grain variation
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    tone = _sine_sweep(n, 200.0, 2400.0, 0.32)
    for i in range(n):
        t = i / float(n)
        tone[i] = int(tone[i] * (t ** 1.5))
    _mix(buf, tone)
    chunks = 32
    for c in range(chunks):
        t0 = (c * n) // chunks
        t1 = ((c + 1) * n) // chunks
        L = t1 - t0
        if L <= 0:
            continue
        cutoff = 300.0 * ((8000.0 / 300.0) ** (c / float(chunks - 1)))
        seg = _pink(L, 0.30)
        _lp(seg, cutoff, 2)
        g = ((c + 1) / float(chunks)) ** 1.5
        for i in range(L):
            seg[i] = int(seg[i] * g)
        _offset_mix(buf, seg, t0)
    n_ticks = 26
    t_start = 0.45 * dur
    for k in range(n_ticks):
        frac = k / float(n_ticks - 1)
        t = t_start + (dur * 0.53) * (frac ** 1.6)
        off = int(SAMPLE_RATE * t)
        L = min(int(SAMPLE_RATE * 0.012), n - off)
        if L <= 16 or off < 0:
            continue
        tick = _pink(L, 0.40)
        _bp(tick, 1800, 6500)
        _env_exp(tick, 1.0, 0.001, 120.0)
        _offset_mix(buf, tick, off, 0.5 + 0.5 * frac)
    _soft_clip(buf, 1.2)
    return _wav(_match_peak(buf, 0.8))

def _gen_riser_8s():
    return _gen_riser(8.0)

def _gen_riser_12s():
    return _gen_riser(12.0)

def _gen_braam(dur=1.8, f0=36.7):
    """Trailer BRAAM: D1 sine sub + octave FM pressure + 80 Hz lowpassed
    pink boom, ~1.8 s exp decay, soft-clipped, -2 dBTP peak. Hits on every
    act cut (0:07, 0:17, 0:29, 0:47)."""
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    sub = _sin(n, f0, 0.55)
    _env_exp(sub, 1.0, 0.001, 2.0)
    _mix(buf, sub)
    press = _fm(n, f0 * 2.0, 0.30, f0, 0.6, decay_rate=3.0)
    _env_exp(press, 1.0, 0.001, 2.4)
    _mix(buf, press)
    boom = _pink(n, 0.40)
    _lp(boom, 80, 3)
    _env_exp(boom, 1.0, 0.001, 2.0)
    _mix(buf, boom)
    _soft_clip(buf, 1.35)
    return _wav(_match_peak(buf, 0.79))

def _gen_braam_downpitch(dur=2.0):
    """End-card sting: D1->26 Hz drop + brown rumble + sparse dark taps."""
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    drop = _sine_sweep(n, 36.7, 26.0, 0.55)
    _env_exp(drop, 1.0, 0.001, 2.2)
    _mix(buf, drop)
    rum = _brown(n, 0.30)
    _lp(rum, 90, 2)
    _env_exp(rum, 1.0, 0.001, 1.8)
    _mix(buf, rum)
    _multitap(buf, [200, 420], [0.3, 0.15], wet=0.3)
    _soft_clip(buf, 1.3)
    return _wav(_match_peak(buf, 0.79))

def _gen_trailer_gun_suppressed():
    """M1 stealth stack (§3 SUPPRESSED_9MM): band pop + low thump +
    quiet metallic tick 5 ms early, dry (no reverb). Peaks 6 dB under the
    unsuppressed stack so the drop reads 2x louder."""
    n = int(SAMPLE_RATE * 0.30)
    buf = _arr(n)
    pop = _pink(int(SAMPLE_RATE * 0.020), 0.9)
    _bp(pop, 500, 2600)
    _env_exp(pop, 1.0, 0.001, 60.0)
    _mix(buf, pop)
    thump = _fm(int(SAMPLE_RATE * 0.12), 90, 0.4, 45, 0.6, decay_rate=14.0)
    _env_exp(thump, 1.0, 0.001, 18.0)
    _offset_mix(buf, thump, int(SAMPLE_RATE * 0.002))
    tick = _pink(int(SAMPLE_RATE * 0.008), 0.35)
    _bp(tick, 2000, 7000)
    _env_exp(tick, 1.0, 0.001, 90.0)
    _offset_mix(buf, tick, 0, 0.4)
    _soft_clip(buf, 1.2)
    return _wav(_match_peak(buf, 0.45))

def _gen_trailer_gun_unsuppressed():
    """Post-drop stack (§3 UNSUPPRESSED): crack + FM body + snap tail."""
    n = int(SAMPLE_RATE * 0.55)
    buf = _arr(n)
    crack = _pink(int(SAMPLE_RATE * 0.012), 1.0)
    _bp(crack, 900, 5200)
    _env_exp(crack, 1.0, 0.001, 120.0)
    _mix(buf, crack)
    body = _fm(int(SAMPLE_RATE * 0.30), 55, 0.7, 110, 1.6, decay_rate=7.0)
    _env_exp(body, 1.0, 0.001, 7.0)
    _offset_mix(buf, body, int(SAMPLE_RATE * 0.003))
    snap = _sine_sweep(int(SAMPLE_RATE * 0.07), 6200, 1700, 0.25)
    _env_exp(snap, 1.0, 0.001, 18.0)
    _offset_mix(buf, snap, int(SAMPLE_RATE * 0.010), 0.32)
    _soft_clip(buf, 1.45)
    return _wav(_match_peak(buf, 0.89))

def _gen_trailer_sniper_stack():
    """M2 sniper stack (§3 SNIPER): dry crack + 35 ms delayed report +
    sub bloom + 170 ms valley slap. Duck music 0.5 s after in the mix."""
    n = int(SAMPLE_RATE * 1.15)
    buf = _arr(n)
    snap = _pink(int(SAMPLE_RATE * 0.006), 1.0)
    _bp(snap, 2500, 7500)
    _env_exp(snap, 1.0, 0.001, 120.0)
    _mix(buf, snap)
    blast = _brown(int(SAMPLE_RATE * 0.16), 0.7)
    _lp(blast, 620, 2)
    _env_exp(blast, 1.0, 0.001, 16.0)
    _offset_mix(buf, blast, int(SAMPLE_RATE * 0.035))
    sub = _fm(int(SAMPLE_RATE * 0.55), 45, 0.34, 22, 0.7, decay_rate=4.8)
    _env_exp(sub, 1.0, 0.001, 5.0)
    _offset_mix(buf, sub, int(SAMPLE_RATE * 0.045))
    _apply_delay(buf, 170, feedback=0.26, wet=0.18)
    _soft_clip(buf, 1.4)
    return _wav(_match_peak(buf, 0.89))

def _gen_trailer_breach_stack():
    """Breach stack (§3 BREACH): structural thud + pitch-dropping sub +
    inharmonic plate rattle at -5 dB. AI4 flashes on the transient."""
    n = int(SAMPLE_RATE * 0.85)
    buf = _arr(n)
    thud = _brown(n, 0.65)
    _lp(thud, 170, 2)
    _env_exp(thud, 1.0, 0.001, 8.0)
    _mix(buf, thud)
    sub = _sine_sweep(int(SAMPLE_RATE * 0.30), 75, 34, 0.5)
    _env_exp(sub, 1.0, 0.001, 8.0)
    _mix(buf, sub)
    plate = _plate(int(SAMPLE_RATE * 0.30), 336.0,
                   [(1.0, 1.0), (2.71, 0.50), (5.06, 0.28)], 0.30, decay=20.0)
    _offset_mix(buf, plate, int(SAMPLE_RATE * 0.006), 0.56)
    _soft_clip(buf, 1.4)
    return _wav(_match_peak(buf, 0.89))

TRAILER_LAZY_GENS = [
    ("squelch_head", _gen_squelch_head),
    ("squelch_tail", _gen_squelch_tail),
    ("riser_8s", _gen_riser_8s),
    ("riser_12s", _gen_riser_12s),
    ("braam", _gen_braam),
    ("braam_downpitch", _gen_braam_downpitch),
    ("trailer_gun_suppressed", _gen_trailer_gun_suppressed),
    ("trailer_gun_unsuppressed", _gen_trailer_gun_unsuppressed),
    ("trailer_sniper_stack", _gen_trailer_sniper_stack),
    ("trailer_breach_stack", _gen_trailer_breach_stack),
]
LAZY_GENS.extend(TRAILER_LAZY_GENS)

# Mission-owned sound sets (e.g. missions.m5.finale_audio) register their
# generators at runtime through AudioManager.register_lazy_generators.

# ── Audio Manager ──

_channels = {}

# Channel 0 is reserved for voice-over (see _init_mixer / audio.voice), so
# named channels start at 1 and pygame's auto-allocation never lands a loop
# on the voice channel.
VOICE_CHANNEL_INDEX = 0


def _ch(ch_id):
    if ch_id not in _channels:
        idx = min(len(_channels) + 1, 31)
        _channels[ch_id] = pygame.mixer.Channel(idx)
    return _channels[ch_id]


# ── Upload OS CRT sounds ──

def _gen_crt_whine():
    """CRT power-on high-voltage whistle (~12 kHz flyback transformer)."""
    dur = 1.2
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    tone = _sin(n, 11800, 0.14)
    for i in range(n):
        wobble = 1.0 + 0.003 * math.sin(i * 0.0008)
        buf[i] = int(tone[i] * wobble)
    harm = _sin(n, 15750, 0.04)
    _mix(buf, harm, 0.6)
    _env_adsr(buf, 0.25, 0.15, 0.35, 0.55, 0.70)
    _soft_clip(buf, 1.0)
    return _wav(buf)


def _gen_crt_thunk():
    """CRT power-off thunk: degauss coil + shadow mask settling."""
    dur = 0.35
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    thump = _fm(n, 110, 0.5, 55, 0.4, decay_rate=18.0)
    _env_exp(thump, 1.0, 0.001, 16.0)
    _mix(buf, thump)
    ring = _sin(n, 420, 0.12)
    _env_exp(ring, 1.0, 0.001, 22.0)
    _mix(buf, ring)
    click = _noise(int(SAMPLE_RATE * 0.008), 0.3)
    _env_exp(click, 1.0, 0.001, 60.0)
    _mix(buf, click)
    _soft_clip(buf, 1.1)
    return _wav(buf)


def _gen_modem_dialup():
    """Classic 2400 baud modem handshake (dial tone → screech → connect)."""
    rng = random.Random(7703)
    dur = 3.0
    n = int(SAMPLE_RATE * dur)
    buf = _arr(n)
    # Dial tone (0.0–0.4s).
    dt_end = int(SAMPLE_RATE * 0.4)
    dt = _sin(dt_end, 350, 0.12)
    dt2 = _sin(dt_end, 440, 0.10)
    for i in range(dt_end):
        dt[i] = int(dt[i] + dt2[i])
    _offset_mix(buf, dt, 0)
    # DTMF pulse (0.4–0.5s).
    dtmf_len = int(SAMPLE_RATE * 0.08)
    dtmf = _sin(dtmf_len, 941, 0.18)
    dtmf2 = _sin(dtmf_len, 1336, 0.15)
    for i in range(dtmf_len):
        dtmf[i] = int(dtmf[i] + dtmf2[i])
    _env_exp(dtmf, 1.0, 0.001, 30.0)
    _offset_mix(buf, dtmf, int(SAMPLE_RATE * 0.4))
    # Ringing (0.5–1.0s).
    ring_dur = int(SAMPLE_RATE * 0.5)
    rt = _sin(ring_dur, 440, 0.10)
    rt2 = _sin(ring_dur, 480, 0.09)
    for i in range(ring_dur):
        rt[i] = int(rt[i] + rt2[i])
        t = i / SAMPLE_RATE
        if not ((t < 0.15) or (0.25 < t < 0.40)):
            rt[i] = 0
    _offset_mix(buf, rt, int(SAMPLE_RATE * 0.5))
    # Answering carrier (1.0–1.3s).
    ced = _sin(int(SAMPLE_RATE * 0.3), 2100, 0.14)
    _env_adsr(ced, 0.05, 0.05, 0.7, 0.1, 0.85)
    _offset_mix(buf, ced, int(SAMPLE_RATE * 1.0))
    # Training screech (1.3–2.5s).
    sc_dur = int(SAMPLE_RATE * 1.2)
    screech = _arr(sc_dur)
    for _ in range(28):
        bl = rng.randint(int(SAMPLE_RATE * 0.02), int(SAMPLE_RATE * 0.08))
        bo = rng.randint(0, max(1, sc_dur - bl))
        freq = rng.uniform(600, 2800)
        burst = _fm(bl, freq, 0.20, freq * rng.uniform(0.5, 2.0),
                    rng.uniform(1.0, 4.0), decay_rate=rng.uniform(8.0, 20.0))
        _env_exp(burst, 1.0, 0.001, rng.uniform(15.0, 35.0))
        _offset_mix(screech, burst, bo)
    bed = _noise(sc_dur, 0.04)
    _resonant_filter(bed, 1500, 0.3, "low")
    _mix(screech, bed)
    _soft_clip(screech, 1.2)
    _offset_mix(buf, screech, int(SAMPLE_RATE * 1.3))
    # Carrier connect (2.5–3.0s).
    carrier = _sin(int(SAMPLE_RATE * 0.5), 1650, 0.12)
    _env_adsr(carrier, 0.05, 0.1, 0.5, 0.5, 0.7)
    _offset_mix(buf, carrier, int(SAMPLE_RATE * 2.5))
    _soft_clip(buf, 1.1)
    return _wav(buf)


class AudioManager:
    def __init__(self):
        self.sounds = {}
        self.master_volume = 0.8
        self.sfx_volume = 1.0       # 0..1 - separate scale for SFX (one-shots + loops)
        self.scheduled = []
        self._loop_channels = {}
        self._loop_base_volumes = {}
        self._duck_frames = 0
        self._duck_factor = 1.0
        self._ambience_names = {"rain", "wind", "ambient_drone",
                              "room_tone", "elec_hum", "rain_inside", "m4_roof_air"}
        self._lazy = dict(LAZY_GENS)
        self.verbose = False
        self._init_mixer()
        self._generate_all()
        
    def register_lazy_generators(self, gens):
        """Add ``(name, generator)`` pairs built on first use (mission-owned sound sets).

        Idempotent: names already generated or already registered are kept.
        """
        for name, gen in gens:
            if name not in self.sounds and name not in self._lazy:
                self._lazy[name] = gen

    def _ensure(self, name):
        """Build a lazily-registered sound on first use, then cache it."""
        s = self.sounds.get(name)
        if s is None and name in self._lazy:
            gen = self._lazy.pop(name)
            try:
                s = _load(gen())   # generators yield WAV bytes, like the eager path
            except Exception:
                s = None
            self.sounds[name] = s
        return s

    def _pick_footstep(self, prefix, count):
        key = f"{prefix}_{_rng_legacy.randint(1, count)}"
        return self.sounds.get(key, self.sounds.get(prefix))
        
    def _init_mixer(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
        except Exception:
            pass
        try:
            pygame.mixer.set_num_channels(32)
            # Keep channel 0 out of Sound.play()'s free-channel search: it is
            # the voice-over channel. Without this a looping ambience bed
            # could grab it, and the ducking pass in update() would then
            # set_volume() the *channel* low - leaving radio VO near-silent.
            pygame.mixer.set_reserved(1)
        except Exception:
            pass
            
    def _generate_all(self):
        gens = [
            ("gunshot", _gen_gunshot),
            ("gunshot_distant", _gen_gunshot_distant),
            ("sniper_crack", _gen_sniper_crack),
            ("bullet_snap", _gen_bullet_snap),
            ("concrete_impact", _gen_concrete_impact),
            ("tinnitus", _gen_tinnitus),
            ("rifle_handle", _gen_rifle_handle),
            ("footstep", _gen_footstep),
            ("footstep_1", _gen_footstep),
            ("footstep_2", _gen_footstep_b),
            ("footstep_3", _gen_footstep_c),
            ("footstep_walk", _gen_footstep_walk),
            ("footstep_walk_1", _gen_footstep_walk),
            ("footstep_walk_2", _gen_footstep_walk_b),
            ("footstep_walk_3", _gen_footstep_walk_c),
            ("melee_hit", _gen_melee_hit),
            ("bullet_impact", _gen_bullet_impact),
            ("bullet_impact_enemy", _gen_bullet_impact_enemy),
            ("door_creak", _gen_door_creak),
            ("door_rattle", _gen_door_rattle),
            ("door_open", _gen_door_open),
            ("reload", _gen_reload),
            ("ambient_drone", _gen_ambient_drone),
            ("rain", _gen_rain),
            ("wind", _gen_wind),
            ("explosion", _gen_explosion),
            ("terminal_glitch", _gen_terminal_glitch),
            ("missile_launch", _gen_missile_launch),
            ("missile_flyby", _gen_missile_flyby),
            ("rig_impact_crack", _gen_rig_impact_crack),
            ("rig_low_boom", _gen_rig_low_boom),
            ("rig_secondary_explosion", _gen_rig_secondary_explosion),
            ("rig_metal_collapse", _gen_rig_metal_collapse),
            ("rig_water_splash", _gen_rig_water_splash),
            ("rig_fire_burst", _gen_rig_fire_burst),
            ("heartbeat", _gen_heartbeat),
            ("menu_click", _gen_menu_click),
            ("menu_hover", _gen_menu_hover),
            ("type_tick", _gen_type_tick),
            ("type_tick_1", _gen_type_tick),
            ("type_tick_2", _gen_type_tick_b),
            ("type_tick_3", _gen_type_tick_c),
            ("radio_static", _gen_radio_static),
            ("radio_chatter", _gen_radio_chatter),
            ("water_drip", _gen_water_drip),
            ("mission_complete", _gen_mission_complete),
            ("breach", _gen_breach),
            ("molotov_throw", _gen_molotov_throw),
            ("molotov_explode", _gen_molotov_explode),
            ("pickup", _gen_pickup),
            ("alarm", _gen_alarm),
            ("empty_click", _gen_empty_click),
            ("glass_shatter", _gen_glass_shatter),
            ("crt_whine", _gen_crt_whine),
            ("crt_thunk", _gen_crt_thunk),
            ("modem_dialup", _gen_modem_dialup),
        ]
        for name, gen in gens:
            try:
                self.sounds[name] = _load(gen())
            except Exception as e:
                print(f"Audio gen failed: {name} - {e}")

        # Optional external Mission 3 alarm MP3.
        # Looks for:
        #   assets/alarm.mp3
        # relative to the game folder/current working directory.
        try:
            self._load_optional_sound(
                "mission3_alarm_loop",
                [
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "alarm.mp3"),
                    os.path.join(os.path.abspath("."), "assets", "alarm.mp3"),
                    os.path.join(os.path.abspath("."), "First try", "assets", "alarm.mp3"),
                    os.path.join(os.path.abspath("."), "Call of Acaristan", "First try", "assets", "alarm.mp3"),
                    r"Call of Acaristan\First try\assets\alarm.mp3",
                ],
            )
        except Exception as e:
            print(f"Optional alarm.mp3 load failed: {e}")
                
    def _effective_volume(self, name, volume):
        duck = self._duck_factor if name in self._ambience_names and self._duck_frames > 0 else 1.0
        if name == "wind":
            volume *= 0.40
        elif name == "rain":
            volume *= 0.55
        elif name == "rain_inside":
            volume *= 0.50
        elif name == "room_tone":
            volume *= 0.55
        elif name == "elec_hum":
            volume *= 0.50
        # SFX scale applies to all sounds EXCEPT streaming music (which is
        # handled separately via pygame.mixer.music.set_volume). This is
        # what makes the Audio → SFX Volume slider actually audible.
        return max(0.0, min(1.0, self.master_volume * self.sfx_volume * volume * duck))

    def play(self, name, volume=1.0, loops=0, channel=None):
        if name in ("footstep", "footstep_walk", "type_tick"):
            variant = f"{name}_{_rng_legacy.randint(1, 3)}"
            s = self._ensure(variant) or self._ensure(name)
            if name == "type_tick":
                volume = min(1.0, volume * 4.5)
        else:
            s = self._ensure(name)
        if s is None:
            return None
        if self.verbose:
            print(f"[audio] {name} vol={volume:.2f}")
        vol = self._effective_volume(name, volume)
        s.set_volume(vol)
        if channel is not None:
            c = _ch(channel)
            c.play(s, loops=loops)
        else:
            c = s.play(loops=loops)
        if c and loops != 0:
            self._loop_channels[name] = c
            self._loop_base_volumes[name] = volume
        return c
        
    def play_random(self, prefix, count=3, volume=1.0, loops=0, channel=None):
        return self.play(f"{prefix}_{_rng_legacy.randint(1, count)}", volume=volume, loops=loops, channel=channel)
        
    def schedule(self, delay_frames, name, volume=1.0, loops=0, channel=None):
        self.scheduled.append({
            "delay": max(0, int(delay_frames)),
            "name": name,
            "volume": volume,
            "loops": loops,
            "channel": channel,
        })
        
    def update(self):
        for item in self.scheduled[:]:
            item["delay"] -= 1
            if item["delay"] <= 0:
                self.play(item["name"], item["volume"], item["loops"], item["channel"])
                self.scheduled.remove(item)
        if self._duck_frames > 0:
            self._duck_frames -= 1
            if self._duck_frames <= 0:
                self._duck_factor = 1.0
            for name, ch in list(self._loop_channels.items()):
                if ch is None:
                    continue
                base = self._loop0_base_volumes.get(name, 1.0) if hasattr(self, '_loop0_base_volumes') else self._loop_base_volumes.get(name, 1.0)
                try:
                    ch.set_volume(self._effective_volume(name, base))
                except Exception:
                    pass
                    
    def duck_ambience(self, frames=90, factor=0.35):
        self._duck_frames = max(self._duck_frames, int(frames))
        self._duck_factor = min(self._duck_factor, max(0.0, min(1.0, factor)))

    def duck_for_radio(self, frames=90, factor=0.35):
        """PLAN_3_AUDIO §2: duck music/ambience beds under radio VO.

        Thin wrapper over duck_ambience so radio call sites need no new
        imports; the trailer stem equivalent is the sidechaincompress
        stage in tools/render_trailer_v2.mux_1080p_trailer_mix.
        """
        self.duck_ambience(frames=frames, factor=factor)
        
    def play_3d(self, name, source_pos, listener_pos, max_dist=800, base_volume=1.0):
        s = self._ensure(name)
        if s is None:
            return None
        dx = source_pos[0] - listener_pos[0]
        dy = source_pos[1] - listener_pos[1]
        dist = math.hypot(dx, dy)
        if dist >= max_dist:
            return None
        attenuation = max(0.0, 1.0 - (dist / max_dist))
        final_vol = base_volume * self.master_volume * self.sfx_volume * attenuation
        pan = dx / max_dist
        pan = max(-1.0, min(1.0, pan))
        left_vol = final_vol * min(1.0, 1.0 - pan)
        right_vol = final_vol * min(1.0, 1.0 + pan)
        channel = s.play()
        if channel:
            channel.set_volume(left_vol, right_vol)
        return channel
        
    def stop(self, name=None, channel=None):
        # Defensive: a sound may be absent (no mixer, failed generation) and the
        # ambience layers call stop() at zone edges - this must never raise.
        if channel is not None and channel in _channels:
            try:
                _channels[channel].stop()
            except Exception:
                pass
        elif name:
            s = self.sounds.get(name)
            if s is not None:
                try:
                    s.stop()
                except Exception:
                    pass
            self._loop_channels.pop(name, None)
            self._loop_base_volumes.pop(name, None)
            
    def stop_all(self):
        for ch in _channels.values():
            ch.stop()
        for name in self.sounds:
            try:
                self.sounds[name].stop()
            except Exception:
                pass
        self._loop_channels.clear()
        self._loop_base_volumes.clear()
        self.scheduled.clear()
        self.stop_epoch = getattr(self, "stop_epoch", 0) + 1

    def hard_stop(self, music=False):
        """Silence everything NOW: one-shots, loops, scheduled cues, ducking,
        voice-over (reserved channel 0) and death screams. Called on quit,
        exit-to-menu and every mission (re)start so nothing from the old
        scene bleeds into the next one. Streaming music only if music=True."""
        self.scheduled.clear()
        self._loop_channels.clear()
        self._loop_base_volumes.clear()
        self._duck_frames = 0
        self._duck_factor = 1.0
        try:
            from audio import voice
            voice.stop()
        except Exception:
            pass
        try:
            pygame.mixer.unpause()       # a paused channel would resume later
            pygame.mixer.stop()          # halts reserved channels too
        except Exception:
            pass
        if music:
            self.stop_music()
        self.stop_epoch = getattr(self, "stop_epoch", 0) + 1
        
    def set_master_volume(self, vol_0_to_100):
        self.master_volume = max(0.0, min(1.0, vol_0_to_100 / 100.0))
        try:
            pygame.mixer.music.set_volume(self.master_volume * getattr(self, "_current_music_vol", 0.5))
        except Exception:
            pass
        
    def play_music(self, filename, volume=0.5):
        """Loads and streams an MP3 music track in the background."""
        import os
        filepath = os.path.join(os.path.dirname(__file__), filename)
        if not os.path.exists(filepath):
            filepath = filename
        if not os.path.exists(filepath):
            print(f"Music file not found: {filename}")
            return False
        try:
            _load_music(filepath)
            self._current_music_vol = volume
            pygame.mixer.music.set_volume(self.master_volume * volume)
            pygame.mixer.music.play(loops=-1)
            return True
        except Exception as e:
            print(f"Failed to play music: {e}")
            return False

    def stop_music(self):
        """Stops the streaming background music."""
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    def set_music_volume(self, volume):
        """Adjusts the streaming music volume dynamically."""
        self._current_music_vol = volume
        try:
            pygame.mixer.music.set_volume(self.master_volume * volume)
        except Exception:
            pass

    def set_sfx_volume(self, volume):
        """Adjusts the SFX volume scale dynamically.

        Affects all one-shot sound effects + looping ambience. Also refreshes
        any currently-looping sounds so the change is audible immediately
        rather than only on the next play().
        """
        self.sfx_volume = max(0.0, min(1.0, float(volume)))
        for name, ch in list(self._loop_channels.items()):
            if ch is None:
                continue
            base = self._loop_base_volumes.get(name, 1.0)
            try:
                ch.set_volume(self._effective_volume(name, base))
            except Exception:
                pass

    def mute_all(self):
        """Pause every playing sound + streaming music. Used by the
        Audio → Mute on Focus Loss setting when the window loses focus."""
        try:
            pygame.mixer.pause()
            pygame.mixer.music.pause()
        except Exception:
            pass

    def unmute_all(self):
        """Resume everything paused by mute_all()."""
        try:
            pygame.mixer.unpause()
            pygame.mixer.music.unpause()
        except Exception:
            pass
        
    def _load_optional_sound(self, name, candidate_paths):
        """Try to load an external sound file into self.sounds[name].

        Used for user-provided assets like assets/alarm.mp3. If loading fails,
        nothing crashes - gameplay can fall back to the procedural sound.
        """
        for path in candidate_paths:
            try:
                if path and os.path.exists(path):
                    self.sounds[name] = _load_sound(path)
                    print(f"Loaded optional sound '{name}': {path}")
                    return True
            except Exception as e:
                print(f"Failed loading optional sound '{name}' from {path}: {e}")
        return False

    def play_mission3_alarm(self, volume=0.22):
        """Start Mission 3 lockdown alarm loop.

        The external alarm.mp3 is likely mastered loud, so this defaults LOW.
        Uses assets/alarm.mp3 if loaded as mission3_alarm_loop.
        Falls back to the procedural alarm if the MP3 is unavailable.
        """
        if "mission3_alarm_loop" in self.sounds:
            return self.play("mission3_alarm_loop", volume=volume, loops=-1, channel="m3_alarm")

        # Fallback procedural alarm, also quieter.
        return self.play("alarm", volume=min(1.0, volume * 0.65), loops=-1, channel="m3_alarm")

    def stop_mission3_alarm(self):
        """Stop Mission 3 lockdown alarm loop."""
        try:
            self.stop("mission3_alarm_loop")
        except Exception:
            pass
        try:
            self.stop("alarm")
        except Exception:
            pass
        try:
            self.stop(channel="m3_alarm")
        except Exception:
            pass

    def get_sound(self, name):
        return self._ensure(name)
        
    def is_playing(self, channel):
        if channel in _channels:
            return _channels[channel].get_busy()
        return False
        
    def fadeout(self, channel, fade_ms=500):
        if channel in _channels:
            _channels[channel].fadeout(fade_ms)

