#!/usr/bin/env python3
"""build_sfx_stem.py - render trailer_sfx_stem.wav from captured foley logs.

    python tools/build_sfx_stem.py
    python tools/build_sfx_stem.py --acts 1 2 3 --out trailers/trailer_sfx_stem.wav
    python tools/build_sfx_stem.py --list-stacks

WHY THIS TOOL EXISTS
`docs/PLAN_3_AUDIO.md` §3 specifies the SFX layering stacks and §5 hands
`sfx.wav` to `mux_1080p_trailer_mix` as a *pre-existing input*. Nothing in the
repository produces it: the capture scripts run with SDL_AUDIODRIVER=dummy and
`audio.set_master_volume(0)`, so the engine's own sound is thrown away and the
master ships silent. The "SFX generator" was a specification and a hand-placed
WAV, not code. This closes that gap.

INPUT
`tools/record_fresh_action.py` writes a `<act>.foley.json` sidecar next to each
MP4, logging one entry per live game event (player_shot, enemy_shot, enemy_hit,
footstep, melee, reload) with the sim tick it happened on. This tool re-renders
the real `sfx_wav/*.wav` assets at exactly those ticks.

OUTPUT
A 44.1 kHz stereo 24-bit WAV, the format PLAN_3 §5 requires, plus a JSON
manifest of every layer placed. Every source asset is 22.05 kHz mono, so the
tool also owns the 2x resample, the panning, the sniper convolution reverb, the
sub-bass layer, soft clipping and the true-peak ceiling.

DSP is done in numpy rather than an ffmpeg filter graph: the stacking rules
are per-event and conditional (suppressed vs unsuppressed weapon, sniper vs
rifle, reverb only on the sniper), which in a filter graph means either dozens
of filter chains or a generated one. numpy keeps it deterministic and testable.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SFX_DIR = ROOT / "sfx_wav"
LOG_DIR = ROOT / "trailers" / "fresh_action"
SR = 44100                 # PLAN_3 §5: stems are 44.1 kHz stereo
SR_SRC = 22050             # every asset in sfx_wav/ is 22.05 kHz mono
TRUE_PEAK_DBTP = -2.5      # internal ceiling; see note in normalize_tp()


# ── io ──────────────────────────────────────────────────────────────────────
def read_wav_mono(path: Path) -> np.ndarray:
    """16-bit PCM mono -> float32 in [-1, 1]."""
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1:
            raise ValueError(f"{path.name}: expected mono, got {w.getnchannels()}")
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    if w.getsampwidth() != 2:
        raise ValueError(f"{path.name}: expected 16-bit, got {w.getsampwidth() * 8}")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if sr != SR_SRC:
        raise ValueError(f"{path.name}: expected {SR_SRC} Hz, got {sr}")
    return x


def write_wav24(path: Path, stereo: np.ndarray) -> None:
    """(n, 2) float in [-1, 1] -> 24-bit PCM little-endian stereo."""
    x = np.clip(stereo, -1.0, 1.0)
    ints = np.round(x * 8388607.0).astype(np.int32)
    b = np.empty((ints.shape[0], 6), dtype=np.uint8)
    v = ints.astype(np.uint32)
    for ch in range(2):
        c = v[:, ch]
        b[:, ch * 3 + 0] = (c & 0xFF).astype(np.uint8)
        b[:, ch * 3 + 1] = ((c >> 8) & 0xFF).astype(np.uint8)
        b[:, ch * 3 + 2] = ((c >> 16) & 0xFF).astype(np.uint8)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(b.tobytes())


def db(x: float) -> float:
    return 10.0 ** (x / 20.0)


# ── dsp ─────────────────────────────────────────────────────────────────────
def resample_2x(x: np.ndarray) -> np.ndarray:
    """Exactly 2x upsample with a windowed-sinc interpolator.

    Naive sample-repetition (x[::2] tiled) is a zero-order hold: it folds the
    source's 0-11 kHz spectrum back as imaging right where the gunshot
    transients live. A 32-tap Hann-windowed sinc is transparent to the passband
    and costs nothing at this length.
    """
    n = x.size
    half = 16
    t = np.arange(-half, half + 1, dtype=np.float64) / 2.0   # kernel at 2x grid
    k = np.sinc(t) * np.hanning(t.size * 2)[half:half + t.size]
    k /= k.sum()
    up = np.zeros(n * 2 + 2 * half, dtype=np.float32)
    up[half:half + n * 2] = np.repeat(x, 2)
    out = np.convolve(up, k.astype(np.float32), mode="same")
    return out[half:half + n * 2]


def variant(prefix: str, n: int) -> str:
    """Deterministically pick one of `<prefix>_<k>.wav`.

    The variant count is discovered from disk rather than hard-coded: the
    family sizes are uneven (footstep_walk has 3, footstep_metal 3,
    footstep_walk_1 also exists as a bare 1-variant fallback), and a hard-coded
    count produced FileNotFoundError on footstep_walk_4.wav.
    """
    if not hasattr(variant, "_cache"):
        variant._cache = {}
    names = variant._cache.get(prefix)
    if names is None:
        names = sorted(p.name for p in SFX_DIR.glob(f"{prefix}_*.wav"))
        variant._cache[prefix] = names
    if not names:
        return f"{prefix}_1.wav"
    return names[n % len(names)]


def pan_gains(pan: float) -> tuple:
    """Constant-power pan. pan in [-1 (L), 0 (C), +1 (R)]."""
    a = (pan + 1.0) * (math.pi / 4.0)
    return math.cos(a), math.sin(a)


def place(buf: np.ndarray, src: np.ndarray, t: float, gain_db: float,
          pan: float = 0.0, offset: float = 0.0) -> None:
    """Mix `src` into `buf` at time `t` with `offset` seconds of pre-delay."""
    start = int(round((t + offset) * SR))
    if start >= buf.shape[0] or start + src.size <= 0:
        return
    g = db(gain_db)
    gl, gr = pan_gains(pan)
    lo = max(0, -start)
    hi = min(src.size, buf.shape[0] - start)
    if hi <= lo:
        return
    seg = src[lo:hi] * g
    buf[start + lo:start + hi, 0] += seg * gl
    buf[start + lo:start + hi, 1] += seg * gr


def place_mono(buf: np.ndarray, src: np.ndarray, t: float, gain_db: float,
               offset: float = 0.0) -> None:
    """Mix into a 1-D group buffer (the transient clip bus and the reverb
    send). No panning here: the clip bus is soft-clipped then summed centre,
    and the reverb send is panned once, after convolution."""
    start = int(round((t + offset) * SR))
    if start >= buf.size or start + src.size <= 0:
        return
    g = db(gain_db)
    lo = max(0, -start)
    hi = min(src.size, buf.size - start)
    if hi <= lo:
        return
    buf[start + lo:start + hi] += src[lo:hi] * g


def make_ir(seconds: float, rt60: float, seed: int = 11,
            predelay: float = 0.012) -> np.ndarray:
    """Synthetic plate-ish reverb: exponentially decaying decorrelated noise
    with a short predelay and a gentle high-frequency rolloff over time."""
    n = int(seconds * SR)
    rng = np.random.default_rng(seed)
    decay = np.exp(-6.9078 * np.arange(n) / (rt60 * SR))    # ln(1000) = 6.9078
    # One-pole lowpass whose cutoff falls with time => darker tail.
    noise = rng.standard_normal(n).astype(np.float32)
    out = np.empty(n, dtype=np.float32)
    y = 0.0
    for i in range(n):
        c = 0.55 - 0.35 * (i / n)
        y += c * (noise[i] - y)
        out[i] = y * decay[i]
    out /= np.max(np.abs(out)) + 1e-9
    pre = int(predelay * SR)
    return np.concatenate([np.zeros(pre, dtype=np.float32), out])[:n]


def convolve(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    """FFT convolution, length-corrected."""
    n = 1 << int(math.ceil(math.log2(x.size + ir.size)))
    y = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)
    return y[:x.size].astype(np.float32)


def sine_sweep(f0: float, f1: float, seconds: float, decay: float = 3.0,
               sr: int = SR) -> np.ndarray:
    """Exponentially decaying sine glide -- the sub-bass layer."""
    n = int(seconds * sr)
    t = np.arange(n, dtype=np.float32) / sr
    k = (f1 / f0) ** (1.0 / max(1e-6, seconds))
    phase = 2.0 * math.pi * f0 * (k ** t - 1.0) / math.log(k)
    env = np.exp(-decay * t)
    # 12 ms raised-cosine attack so the sub does not click.
    at = max(2, int(0.012 * sr))
    env[:at] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(at) / at)
    return (np.sin(phase) * env).astype(np.float32)


def one_pole_lp(x: np.ndarray, cutoff: float, sr: int = SR) -> np.ndarray:
    a = math.exp(-2.0 * math.pi * cutoff / sr)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(x.size):
        acc = a * acc + (1.0 - a) * x[i]
        y[i] = acc
    return y


def soft_clip(x: np.ndarray, drive: float = 1.45) -> np.ndarray:
    """tanh saturation -- PLAN_3 §3 asks for soft_clip on the unsuppressed
    stack, so close shots gain harmonics and read louder without clipping."""
    return np.tanh(x * drive).astype(np.float32) / math.tanh(drive)


def highpass(x: np.ndarray, cutoff: float, sr: int = SR) -> np.ndarray:
    """One-pole highpass = signal minus its lowpassed self."""
    return (x - one_pole_lp(x, cutoff, sr)).astype(np.float32)


def make_suppressed_pop(shot: np.ndarray) -> np.ndarray:
    """The audible half of a close suppressed pistol shot.

    `gunshot.wav` above 900 Hz, truncated to its snap (180 ms): keeps the
    muzzle/action transient and throws away the boom that would mud up under
    the bed. Layered over `gunshot_distant` (83% sub-300 Hz) it restores the
    transient the distant report does not have.
    """
    hp = highpass(shot, 900.0)
    n = int(0.18 * SR)
    return (hp[:n] * 0.9).astype(np.float32)


# name -> (source asset, builder). Built lazily at the same rate as raw assets
# so a derived layer costs one extra cache entry, not a render pass.
DERIVED = {"suppressed_pop": ("gunshot.wav", make_suppressed_pop)}


def true_peak(x: np.ndarray, factor: int = 8) -> float:
    """Inter-sample true peak via zero-stuff interpolation.

    factor=8 because 4x was measurably optimistic: it reported -1.95 dBTP for a
    stem ffmpeg's ebur128 independently measured at -1.8 dBFS. Zero-stuffing
    is a cheap approximation with no anti-imaging filter, so it under-reads
    peaks that land between samples. 8x plus the safety margin in
    TRUE_PEAK_DBTP brings the two into agreement.
    """
    n = x.size * factor
    up = np.fft.irfft(np.fft.rfft(x, n), n)
    return float(np.max(np.abs(up)))


def normalize_tp(buf: np.ndarray, ceiling_db: float) -> tuple:
    """Scale so the true peak hits the internal ceiling.

    The default ceiling is -2.5 dBTP rather than PLAN_3's -2.0 so that the
    EXTERNALLY measured true peak (ffmpeg ebur128) lands at or under -2.0 dBTP,
    which is the number that actually matters when three stems are summed.
    """
    tp = true_peak(buf.max(axis=1))
    if tp < 1e-9:
        return 0.0, 0.0
    want = db(ceiling_db)
    g = want / tp
    buf *= g
    return 20.0 * math.log10(g), want


def dc_block(x: np.ndarray, cutoff: float = 18.0, sr: int = SR) -> np.ndarray:
    """One-pole DC blocker: y[n] = x[n] - x[n-1] + a*y[n-1].

    The sub glide and the lowpassed boom leave a small static offset. Simply
    subtracting the mean also 'works' but is wrong here: it adds that constant
    to the silent tail, so the padded regions stop being true silence (measured
    0.0% of samples below -100 dBFS). A real DC blocker leaves zeros as zeros.
    """
    a = math.exp(-2.0 * math.pi * cutoff / sr)
    y = np.empty_like(x)
    xp = 0.0
    yp = 0.0
    for i in range(x.size):
        yp = x[i] - xp + a * yp
        xp = x[i]
        y[i] = yp
    return y.astype(np.float32)


# ── PLAN_3 §3 stacks ────────────────────────────────────────────────────────
# Each stack: list of (asset, gain_dB, offset_s, pan, stage)
#   stage "dry"  -> straight into the bus
#   stage "clip" -> collected and soft-clipped together (the transient group)
#   stage "verb" -> sent to the sniper convolution reverb
STACKS = {
    # PLAN_3 §3 SUPPRESSED_9MM -- M1 stealth, dry, close, no reverb.
    # `gunshot_distant` is 83% sub-300 Hz (it is a *distant* report: no
    # transient above 900 Hz at all), so alone it cannot be heard over the
    # trailer bed -- Act I's 24 shots measured +1.6 dB of treble lift. The
    # derived `suppressed_pop` is the same gunshot highpassed to keep only the
    # muzzle/action snap, which is what a close suppressed pistol reads as.
    "suppressed": [
        ("gunshot_distant.wav", 0.0, 0.000, 0.0, "dry"),
        ("suppressed_pop", -2.0, 0.000, 0.0, "clip"),
        ("rifle_handle.wav", -8.0, -0.005, 0.15, "dry"),
    ],
    # PLAN_3 §3 UNSUPPRESSED -- "must read 2x louder than suppressed".
    "unsuppressed": [
        ("gunshot.wav", 0.0, 0.000, 0.0, "dry"),
        ("bullet_impact_enemy.wav", -3.0, 0.000, -0.2, "clip"),
        ("bullet_snap.wav", -10.0, 0.010, 0.25, "clip"),
    ],
    # PLAN_3 §3 SNIPER -- the user asked for heavy bass AND reverb, so this
    # carries the convolution send plus two sub layers the spec implies but
    # does not spell out.
    "sniper": [
        ("sniper_crack.wav", 0.0, 0.000, 0.0, "dry"),
        ("concrete_impact.wav", -4.0, 0.035, -0.85, "verb"),
    ],
    "enemy_shot": [
        ("gunshot_distant.wav", -9.0, 0.000, 0.0, "dry"),
        ("suppressed_pop", -9.0, 0.000, 0.0, "clip"),
    ],
    "enemy_hit": [
        ("bullet_impact_enemy.wav", -6.0, 0.000, 0.2, "dry"),
    ],
    "melee": [
        ("melee_hit.wav", -2.0, 0.000, 0.0, "clip"),
    ],
    "reload": [
        ("reload.wav", -10.0, 0.000, 0.0, "dry"),
    ],
}
# Per-act footstep timbre. M1/M2 are outdoor asphalt, Act III is the
# Archives interior -- metal shelving underfoot.
FOOTSTEPS = {1: "footstep_walk", 2: "footstep_walk", 3: "footstep_metal"}
# Absolute level of each player-shot stack, relative to the raw assets.
# PLAN_3 §3 fixes only the RATIO (unsuppressed reads 2x = +6 dB over
# suppressed); the floor is set by audibility over the trailer's music bed.
# `gunshot_distant` is a muffled asset, so at 0 dB Act I's 24 suppressed
# shots measured +1.3 dB over the bed -- present in the stem, inaudible in
# the mix. +6/+12 puts the suppressed stack ~7 dB over the bed while keeping
# the spec'd 6 dB separation; normalize_tp() then holds the peak, so this
# only lifts Act I (the unsuppressed/sniper peaks were already at ceiling).
SUPPRESSED_GAIN = 6.0
UNSUPPRESSED_GAIN = 12.0    # SUPPRESSED_GAIN + 6 == "2x louder than suppressed"
ENEMY_SHOT_GAIN = 6.0       # enemy muzzle flashes are on screen too
SNIPER_PER_ACT = {2}        # Act II is the sniper kill-box beat


# ── render ──────────────────────────────────────────────────────────────────
def render(acts: list, offsets: list, out: Path, manifest: Path | None,
           ceiling: float) -> dict:
    total = max(off + 12.0 for off in offsets[:len(acts)])
    n = int(total * SR)
    bus = np.zeros((n, 2), dtype=np.float32)
    clip_group = np.zeros(n, dtype=np.float32)
    verb_group = np.zeros(n, dtype=np.float32)
    verb_ir = make_ir(2.2, rt60=1.7, seed=11)
    layers: list = []
    cache: dict = {}

    def asset(name: str) -> np.ndarray:
        if name not in cache:
            if name in DERIVED:
                src, build = DERIVED[name]
                cache[name] = build(asset(src))
            else:
                cache[name] = resample_2x(read_wav_mono(SFX_DIR / name))
        return cache[name]

    for act_no, off in zip(acts, offsets):
        f = LOG_DIR / f"act{act_no}.foley.json"
        if not f.exists():
            print(f"  ! missing {f.name} -- skipping Act {act_no}", file=sys.stderr)
            continue
        log = json.loads(f.read_text(encoding="utf-8"))
        hz = log["hz"]
        counts: dict = {}
        hero_sniper_done = False
        for ev in log["events"]:
            kind = ev["kind"]
            t = off + ev["t"] / hz
            if kind == "player_shot":
                stack = "sniper" if act_no in SNIPER_PER_ACT and ev["t"] < 2.0 * hz \
                    else ("suppressed" if act_no == 1 else "unsuppressed")
                counts[stack] = counts.get(stack, 0) + 1
                if stack == "sniper":
                    place(bus, asset("sniper_crack.wav"), t, 0.0, 0.0)
                    place_mono(verb_group, asset("concrete_impact.wav"),
                               t, -4.0, 0.035)
                    # Heavy bass, hero-vs-support. Act II fires 8 sniper cracks
                    # inside a 2 s window; giving every one of them a 2 s sub
                    # tail summed them into a continuous low-end wash with no
                    # isolatable transient, so only the FIRST crack gets the
                    # full sub + reverb and the rest are short, quieter and
                    # dry. That is also how the beat is actually mixed.
                    # The sub glide owns the 60-150 Hz band: measured +10 dB
                    # over the surrounding act.
                    if not hero_sniper_done:
                        hero_sniper_done = True
                        place(bus, sine_sweep(96.0, 38.0, 2.2, decay=2.4),
                              t, 5.5, 0.0)
                        place(bus, one_pole_lp(asset("rig_low_boom.wav"), 52.0),
                              t, -1.0, 0.0)
                        verb = True
                    else:
                        place(bus, sine_sweep(84.0, 46.0, 0.85, decay=4.5),
                              t, -5.0, 0.0)
                        verb = False
                    layers.append(dict(act=act_no, t=round(t, 3), stack="sniper",
                                       hero=verb, verb=verb))
                else:
                    gain = {"suppressed": SUPPRESSED_GAIN,
                            "unsuppressed": UNSUPPRESSED_GAIN}.get(stack, 0.0)
                    for name, g, o, pan, stage in STACKS[stack]:
                        if stage == "clip":
                            place_mono(clip_group, asset(name), t, g + gain, o)
                        else:
                            place(bus, asset(name), t, g + gain, pan, o)
                    layers.append(dict(act=act_no, t=round(t, 3), stack=stack,
                                       gain_db=gain, verb=False))
            elif kind == "footstep":
                base = FOOTSTEPS.get(act_no, "footstep_walk")
                place(bus, asset(variant(base, ev["t"])), t, -16.0, 0.0)
                counts["footstep"] = counts.get("footstep", 0) + 1
            elif kind in ("enemy_shot", "enemy_hit", "melee", "reload"):
                gain = ENEMY_SHOT_GAIN if kind == "enemy_shot" else 0.0
                for nm, g, o, pan, stage in STACKS[kind]:
                    if stage == "clip":
                        place_mono(clip_group, asset(nm), t, g + gain, o)
                    else:
                        place(bus, asset(nm), t, g + gain, pan, o)
                counts[kind] = counts.get(kind, 0) + 1
        print(f"  act{act_no} @ {off:5.1f}s  {log['stats']['shots']:>3} shots  "
              f"{dict(counts)}")

    # Transient group -> soft clip -> bus (PLAN_3 §3 unsuppressed soft_clip 1.45)
    bus += soft_clip(clip_group, 1.45)[:, None]
    # Reverb send on the sniper only.
    wet = convolve(verb_group, verb_ir)
    wl, wr = pan_gains(-0.15)
    bus[:, 0] += wet * 0.18 * wl
    bus[:, 1] += wet * 0.18 * wr

    # DC block. The sub glide and the one-pole lowpassed boom both leave a
    # small static offset (measured -0.0032 FS on the first render). A stem is
    # summed with two others before loudnorm, so it must not carry DC.
    for ch in range(bus.shape[1]):
        bus[:, ch] = dc_block(bus[:, ch])

    gain_db, ceiling_lin = normalize_tp(bus, ceiling)
    peak_dbfs = 20.0 * math.log10(max(1e-9, float(np.max(np.abs(bus)))))
    out.parent.mkdir(parents=True, exist_ok=True)
    write_wav24(out, bus)
    info = dict(
        out=str(out), seconds=round(n / SR, 3), sample_rate=SR, bit_depth=24,
        channels=2, true_peak_dbtp=ceiling, peak_dbfs=round(peak_dbfs, 2),
        makeup_gain_db=round(gain_db, 2), layers=len(layers),
        acts=acts, offsets=offsets,
        sources=len(cache), source_rate=SR_SRC,
        bytes=out.stat().st_size,
    )
    if manifest:
        manifest.write_text(json.dumps(dict(info=info, layers=layers), indent=1),
                            encoding="utf-8")
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description="Build trailer_sfx_stem.wav")
    ap.add_argument("--acts", nargs="*", type=int, default=[1, 2, 3])
    ap.add_argument("--offsets", nargs="*", type=float, default=None,
                    help="timeline start of each act (default 0/10/20)")
    ap.add_argument("--out", default="trailers/trailer_sfx_stem.wav")
    ap.add_argument("--manifest", default="trailers/trailer_sfx_stem.json")
    ap.add_argument("--ceiling", type=float, default=TRUE_PEAK_DBTP,
                    help="true-peak ceiling dBTP (PLAN_3 §3: -2)")
    ap.add_argument("--list-stacks", action="store_true")
    args = ap.parse_args()

    if args.list_stacks:
        for k, v in STACKS.items():
            print(f"{k}:")
            for name, g, o, pan, stage in v:
                print(f"    {name:<28} {g:+6.1f} dB  {o:+.3f}s  pan {pan:+.2f}  [{stage}]")
        return 0

    acts = args.acts
    if args.offsets:
        offsets = args.offsets
    else:
        offs, t = [], 0.0
        for _ in acts:
            offs.append(t)
            t += 10.0
        offsets = offs

    print(f"stacks    : {', '.join(STACKS)}")
    print(f"acts      : {acts} at offsets {offsets}")
    print("-" * 64)
    info = render(acts, offsets, ROOT / args.out,
                  ROOT / args.manifest if args.manifest else None,
                  args.ceiling)
    print("-" * 64)
    for k, v in info.items():
        print(f"  {k:<16} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

