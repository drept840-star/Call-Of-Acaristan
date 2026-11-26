"""Batch packer, silence/DP auto-splitter, and manifest sync for AI Studio VO.

Turns 276 individual missing voice lines into ~30 short copy-paste scripts for
Google AI Studio (or any single-speaker TTS web UI), then slices each exported
WAV back into clean, normalized ``assets/voice/<Speaker>/VO_xxx.ogg`` (or
``.wav``) takes and updates ``KNOWN_MISSING_AUDIO``.

Usage:
    python tools/vo_batch.py status
    python tools/vo_batch.py make-refs
    python tools/vo_batch.py pack [--batch-size 12] [--speaker MARU] [--redo-bodi]
    python tools/vo_batch.py split [--dry-run] [--batch ID] [--file PATH]
    python tools/vo_batch.py sync-manifest [--dry-run]
    python tools/vo_batch.py colab-pack [--redo-bodi]
    python tools/vo_batch.py colab-import PATH_TO_VO_GENERATED_ZIP
    python tools/vo_batch.py ingest SPEAKER DROP_FOLDER [--dry-run] [--align]
"""
import argparse
import array
import ast
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
import zipfile
from pathlib import Path

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
VOICE_DIR = ROOT / "assets" / "voice"
MANIFEST_PATH = SRC / "audio" / "voice_manifest.py"
DEFAULT_OUT = ROOT / "build" / "vo_batches"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    import numpy as _np
except Exception:
    _np = None

from audio import voice  # noqa: E402
from audio.voice_manifest import KNOWN_MISSING_AUDIO, VOICE_LINES  # noqa: E402

AUDIO_EXTS = (".wav", ".ogg", ".mp3", ".flac", ".m4a")
BAKED_SCREAMS = frozenset({"VO_110", "VO_115", "VO_116"})

# (group_id, target_folder, style_direction)
GROUP_SPECS = {
    "00_NARRATOR": (
        "NARRATOR",
        "Stark, literary Eastern European noir male narrator in his 40s-50s. "
        "Measured, low, unhurried documentary weight, never melodramatic.",
    ),
    "01_RETARDOVICI": (
        "Retardovici",
        "Cold, polished, calculating Eastern European head of state in his late 50s. "
        "Calm authority, dry contempt, never raises his voice.",
    ),
    "02_UCILEV": (
        "Ucilev",
        "Flat, clinical, unhurried male special-forces operator in his 30s. "
        "Low register, dead calm, zero theatricality.",
    ),
    "03_MARU": (
        "Maru",
        "Weathered, slightly raspy Eastern European resistance operative (30s-40s). "
        "Grounded, urgent in combat, dry dark humour when quiet.",
    ),
    "04_VASILE": (
        "Vasile",
        "Match existing Captain Vasile voice: steady, weary senior officer (40s-50s). "
        "Controlled authority, quiet guilt underneath.",
    ),
    "05_BIRIBEL": (
        "Biribel",
        "Match existing Biribel voice: terse, stoic male operator in his late 20s-30s. "
        "Low, clipped delivery, dry realism, never melodramatic.",
    ),
    "06_BODI": (
        "Bodi",
        "Match existing Bodi voice: grounded rural Eastern European farmer (40s-50s). "
        "Dry deadpan humour on the farm, steady grit under fire.",
    ),
    "07_ALEX": (
        "Alex",
        "Young, energetic, slightly nervous Eastern European resistance runner (early 20s). "
        "Quick cadence, earnest, tense under fire.",
    ),
    "08_VOLKOV": (
        "Volkov",
        "Match existing Volkov voice: sharp, cynical middle-aged fixer/informant. "
        "Wry, tired, quietly resigned in his final lines.",
    ),
    "09_ANCHOR": (
        "Anchor",
        "Formal state television news anchor. Crisp, flat, rehearsed broadcast cadence.",
    ),
    "10_PA_SYSTEM": (
        "PA",
        "Authoritative state loudspeaker / police dispatch announcer. "
        "Clipped, official, unemotional (radio/PA filter is applied automatically in-game).",
    ),
    "11_GUARD_COMMS": (
        "Guard",
        "Terse military/guard radio operators under stress. "
        "Short tactical shouts and clipped reports (radio filter applied in-game).",
    ),
    "12_ANDREI_M": (
        "Andrei_M",
        "Flustered, territorial young IT administrator in his 20s. "
        "High-strung, indignant, slightly comedic panic.",
    ),
    "13_HUNGRY_KID": (
        "NPCs",
        "Quiet, exhausted young street kid (pre-teen). Soft, raspy, grateful.",
    ),
    "14_OLD_WOMAN": (
        "NPCs",
        "Frail, weary elderly Eastern European woman (70s). "
        "Quiet, earnest, hushed warning tone.",
    ),
    "15_DETAINED_MAN": (
        "NPCs",
        "Terrified working-class civilian man (30s-40s). Breathless, pleading, relieved.",
    ),
    "16_SOLDIERS_A": (
        "NPCs",
        "Gruff working-class checkpoint soldier (30s). Low, cautious, weary.",
    ),
    "17_SOLDIERS_B": (
        "NPCs",
        "Younger enlisted guard/quartermaster (20s-30s). Matter-of-fact, slightly tense.",
    ),
    "18_BALACEANU": (
        "Balaceanu",
        "Match existing Balaceanu voice: furious, sharp authoritarian official yelling into a mic.",
    ),
    "19_GABI": (
        "Gabi",
        "Match existing Gabi voice: calm squadmate doing tactical reconnaissance.",
    ),
    "20_DARIUS": (
        "Darius",
        "Match existing Darius voice: tense squadmate reporting radio interference.",
    ),
    "21_SEBY": (
        "Seby",
        "Match existing Seby voice: alert young squadmate spotting a glint.",
    ),
}

SPEAKER_TO_GROUP = {
    "NARRATOR": "00_NARRATOR",
    "PRESIDENT RETARDOVICI": "01_RETARDOVICI",
    "PRESIDENT": "01_RETARDOVICI",
    "RETARDOVICI": "01_RETARDOVICI",
    "UCILEV": "02_UCILEV",
    "MARU": "03_MARU",
    "MARU (REPLY)": "03_MARU",
    "VASILE": "04_VASILE",
    "CAPTAIN VASILE": "04_VASILE",
    "BIRIBEL": "05_BIRIBEL",
    "BODI": "06_BODI",
    "ALEX": "07_ALEX",
    "VOLKOV": "08_VOLKOV",
    "ANCHOR": "09_ANCHOR",
    "PA SYSTEM": "10_PA_SYSTEM",
    "IPA DISPATCH": "10_PA_SYSTEM",
    "GUARD": "11_GUARD_COMMS",
    "GUARD RADIO": "11_GUARD_COMMS",
    "LOYALIST COMMS": "11_GUARD_COMMS",
    "LOYALIST COMMS (JAMMED)": "11_GUARD_COMMS",
    "INTERCEPT": "11_GUARD_COMMS",
    "ANDREI M.": "12_ANDREI_M",
    "HUNGRY KID": "13_HUNGRY_KID",
    "OLD WOMAN": "14_OLD_WOMAN",
    "DETAINED MAN": "15_DETAINED_MAN",
    "KOVAC": "16_SOLDIERS_A",
    "DESK SERGEANT": "16_SOLDIERS_A",
    "CIOCAN": "16_SOLDIERS_A",
    "SANDU": "17_SOLDIERS_B",
    "OLD SQUADMATE": "17_SOLDIERS_B",
    "QUARTERMASTER": "17_SOLDIERS_B",
    "BALACEANU": "18_BALACEANU",
    "BALACEANU (PA)": "18_BALACEANU",
    "GABI": "19_GABI",
    "DARIUS": "20_DARIUS",
    "SEBY": "21_SEBY",
}

# Clean in-character anchor sentences for Qwen3-TTS VoiceDesign (only used when
# a character has no existing clean reference recordings in assets/voice/).
DESIGN_ANCHORS = {
    "01_RETARDOVICI": "Order is not given to a nation by speeches. It is held quietly, while everyone else sleeps.",
    "02_UCILEV": "Same intake, same rifle, same cold morning. Only one of us stopped following orders.",
    "03_MARU": "Keep your head down and watch the alley. The Guard moves fast once the streetlamps go out.",
    "06_BODI": "Rain's coming over the ridge again. Shut the barn gate and check your boots before coming inside.",
    "07_ALEX": "Wait up, I almost got pinned at the corner! Keep moving, the trucks are already on the hill.",
    "09_ANCHOR": "Good evening. State authorities confirm curfew remains in effect across the capital until further notice.",
    "10_PA_SYSTEM": "Attention all units. Curfew is in effect across the district. Report all unauthorized movement immediately.",
    "11_GUARD_COMMS": "Squad two in position on the avenue. Visual on armed hostile near the loading bay, moving in.",
    "12_ANDREI_M": "Hey! Step away from that terminal right now, nobody touches the server rack without my clearance!",
    "13_HUNGRY_KID": "Please sir, it's been two days since I ate anything. The patrols took everything from the block.",
    "14_OLD_WOMAN": "Listen carefully, soldier, and keep your voice down. The guards wrote the passcode on the desk notes.",
    "15_DETAINED_MAN": "I swear I don't know anything, I just carried the bundles! Please don't hand me over to them.",
    "16_SOLDIERS_A": "Hold it right there. Long night on the checkpoint, keep moving before the patrol circles back.",
    "17_SOLDIERS_B": "Sign for your kit and move along. New orders came down from command an hour ago.",
    "20_DARIUS": "Radio's breaking up down here, whole channel is full of static. Watch the overpass.",
}

PAUSE_RULE = (
    "Deliver each paragraph as a separate voice-over take with a FULL 2.5-second "
    "complete silent pause between paragraphs. Within a single paragraph, speak "
    "normally with only brief natural pauses. Read ONLY the exact text below; "
    "do not add commentary, numbering, or extra words."
)


def _group_for(vo_id, speaker):
    sp = (speaker or "").strip().upper()
    if sp == "ENEMY":
        return "16_SOLDIERS_A" if vo_id == "VO_208" else "17_SOLDIERS_B"
    gid = SPEAKER_TO_GROUP.get(sp)
    if gid:
        return gid
    slug = re.sub(r"[^A-Z0-9]+", "_", sp).strip("_") or "MISC"
    return f"99_{slug}"


def _folder_and_style(gid):
    if gid in GROUP_SPECS:
        return GROUP_SPECS[gid]
    folder = gid.split("_", 1)[1].title() if "_" in gid else gid.title()
    return folder, "Grounded Eastern European noir tone, natural restrained delivery."


def _resolve_speaker_dir(folder_name):
    """Reuse an existing assets/voice/<Folder> if it matches case-insensitively."""
    if VOICE_DIR.is_dir():
        low = folder_name.lower()
        for child in sorted(VOICE_DIR.iterdir()):
            if child.is_dir() and child.name != "_radio_cache" and child.name.lower() == low:
                return child
    return VOICE_DIR / folder_name


def _clean_for_tts(text):
    """Prepare manifest text for TTS without altering canonical words."""
    t = (text or "").replace("\u2026", "...")
    t = re.sub(r"\s*/\s*", " ", t)
    t = re.sub(r"\s*\n+\s*", " ", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def _balanced_chunks(items, max_size):
    n = len(items)
    if n <= max_size:
        return [items]
    k = math.ceil(n / max_size)
    base, rem = divmod(n, k)
    out, pos = [], 0
    for i in range(k):
        sz = base + (1 if i < rem else 0)
        out.append(items[pos:pos + sz])
        pos += sz
    return out


def _missing_lines():
    voice._scan_files()
    out = []
    for vo_id, speaker, text in VOICE_LINES:
        if not voice.has_file(vo_id):
            out.append((vo_id, speaker, text))
    return out


# ---------------------------------------------------------------------------
# Audio I/O & DSP (stdlib + optional numpy + optional ffmpeg for .ogg)
# ---------------------------------------------------------------------------
def _read_wav_pcm(path):
    with wave.open(str(path), "rb") as w:
        chans = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        nframes = w.getnframes()
        raw = w.readframes(nframes)
    if nframes == 0:
        raise RuntimeError(f"Empty WAV: {path}")
    if _np is not None:
        if sw == 2:
            data = _np.frombuffer(raw, dtype="<i2").astype(_np.float32) / 32768.0
        elif sw == 1:
            data = (_np.frombuffer(raw, dtype=_np.uint8).astype(_np.float32) - 128.0) / 128.0
        elif sw == 3:
            b = _np.frombuffer(raw, dtype=_np.uint8).reshape(-1, 3)
            v = (b[:, 0].astype(_np.int32)
                 | (b[:, 1].astype(_np.int32) << 8)
                 | (b[:, 2].astype(_np.int32) << 16))
            v = _np.where(v >= 0x800000, v - 0x1000000, v)
            data = v.astype(_np.float32) / 8388608.0
        elif sw == 4:
            data = _np.frombuffer(raw, dtype="<i4").astype(_np.float32) / 2147483648.0
        else:
            raise RuntimeError(f"Unsupported sample width {sw} in {path}")
        if chans > 1:
            data = data.reshape(-1, chans).mean(axis=1)
        return data, sr
    # Pure-Python fallback
    if sw == 2:
        arr = array.array("h")
        arr.frombytes(raw)
        if sys.byteorder != "little":
            arr.byteswap()
        scale = 1.0 / 32768.0
        if chans == 1:
            mono = [v * scale for v in arr]
        else:
            inv = scale / chans
            mono = [sum(arr[i:i + chans]) * inv for i in range(0, len(arr), chans)]
        return mono, sr
    if sw == 3:
        mono = []
        step = 3 * chans
        inv = 1.0 / (8388608.0 * chans)
        for i in range(0, len(raw), step):
            acc = 0
            for c in range(chans):
                o = i + 3 * c
                v = raw[o] | (raw[o + 1] << 8) | (raw[o + 2] << 16)
                if v >= 0x800000:
                    v -= 0x1000000
                acc += v
            mono.append(acc * inv)
        return mono, sr
    raise RuntimeError(f"Unsupported sample width {sw} without numpy: {path}")


def _load_audio_mono(path):
    path = Path(path)
    if path.suffix.lower() == ".wav":
        try:
            return _read_wav_pcm(path)
        except wave.Error:
            pass
    ff = shutil.which("ffmpeg")
    if not ff:
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=24000, size=-16, channels=1)
            rate, size, chans = pygame.mixer.get_init()
            if abs(size) != 16:
                raise RuntimeError("pygame mixer is not 16-bit")
            raw = pygame.mixer.Sound(str(path)).get_raw()
            if _np is not None:
                data = _np.frombuffer(raw, dtype="<i2").astype(_np.float32) / 32768.0
                if chans > 1:
                    data = data.reshape(-1, chans).mean(axis=1)
                return data, rate
            arr = array.array("h")
            arr.frombytes(raw)
            scale = 1.0 / 32768.0
            if chans == 1:
                return [v * scale for v in arr], rate
            inv = scale / chans
            return [sum(arr[i:i + chans]) * inv for i in range(0, len(arr), chans)], rate
        except Exception as exc:
            raise RuntimeError(
                f"Cannot decode {path.name} without ffmpeg (pygame fallback failed: {exc})"
            )
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(
            [ff, "-y", "-hide_banner", "-loglevel", "error",
             "-i", str(path), "-ac", "1", "-ar", "24000", "-sample_fmt", "s16", str(tmp_path)],
            check=True,
        )
        return _read_wav_pcm(tmp_path)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _rms_envelope(samples, sr, hop_s=0.01):
    hop = max(1, int(sr * hop_s))
    n_win = len(samples) // hop
    if n_win <= 0:
        return [0.0], hop_s
    if _np is not None and isinstance(samples, _np.ndarray):
        blk = samples[:n_win * hop].reshape(n_win, hop)
        env = _np.sqrt(_np.mean(blk * blk, axis=1)).tolist()
        return env, hop / float(sr)
    env = []
    for i in range(n_win):
        s0 = i * hop
        seg = samples[s0:s0 + hop]
        env.append(math.sqrt(sum(x * x for x in seg) / hop))
    return env, hop / float(sr)


def _find_islands(env, dt, merge_gap_s=0.18, min_island_s=0.07):
    if not env:
        return []
    peak = max(env)
    if peak < 0.008:
        return []
    srt = sorted(env)
    noise = srt[int(len(srt) * 0.15)]
    thr = max(0.0055, min(peak * 0.18, noise * 4.0 + 0.004))
    raw = []
    in_seg = False
    start = 0
    for i, e in enumerate(env):
        if e > thr and not in_seg:
            in_seg = True
            start = i
        elif e <= thr and in_seg:
            in_seg = False
            raw.append((start, i))
    if in_seg:
        raw.append((start, len(env)))
    if not raw:
        return []

    # Merge micro-gaps (plosives / brief consonant stops)
    merged = [list(raw[0])]
    for s, e in raw[1:]:
        if (s - merged[-1][1]) * dt <= merge_gap_s:
            merged[-1][1] = e
        else:
            merged.append([s, e])

    # Drop isolated tiny clicks (keep loud short bursts like "Go!")
    clean = []
    for s, e in merged:
        dur = (e - s) * dt
        seg_pk = max(env[s:e])
        if dur < min_island_s and seg_pk < max(0.06, peak * 0.25):
            continue
        clean.append((s * dt, e * dt))
    return clean


def _partition_islands_dp(islands, units):
    """Partition K >= N speech islands into exactly N takes using DP.

    Balances silent-gap length against each line's expected speech duration so
    internal sentence pauses stay merged while inter-take pauses split cleanly.
    """
    k = len(islands)
    n = len(units)
    if k < n:
        raise RuntimeError(f"Only {k} speech islands found for {n} expected lines")
    if n == 1:
        return [(islands[0][0], islands[-1][1])]
    if k == n:
        return list(islands)

    gaps = [max(0.0, islands[i][0] - islands[i - 1][1]) for i in range(1, k)]
    srt_gaps = sorted(gaps, reverse=True)
    # The (N-1)-th largest gap estimates the real inter-take pause length.
    pause_ref = max(0.55, min(2.6, srt_gaps[min(len(srt_gaps) - 1, n - 2)]))
    split_good = pause_ref * 0.72
    internal_bad = pause_ref * 0.85

    # Estimate speaking rate from total speech + short internal pauses
    speech_sum = sum(e - s for s, e in islands)
    short_gaps = sum(g for g in gaps if g < split_good)
    rate = max(0.025, min(0.14, (speech_sum + short_gaps) / max(1.0, sum(units))))

    # Prefix sum of big-internal-gap penalty so inner cost is O(1)
    big_pen = [0.0] * k
    for i in range(1, k):
        g = gaps[i - 1]
        pen = 1.9 * (g / pause_ref) if g >= internal_bad else 0.0
        big_pen[i] = big_pen[i - 1] + pen

    INF = float("inf")
    dp = [[INF] * (n + 1) for _ in range(k + 1)]
    prev_idx = [[-1] * (n + 1) for _ in range(k + 1)]
    dp[0][0] = 0.0

    for j in range(1, n + 1):
        exp_dur = max(0.18, units[j - 1] * rate)
        i_min = j
        i_max = k - (n - j)
        for i in range(i_min, i_max + 1):
            p_min = j - 1
            p_max = i - 1
            if j == 1:
                p_min = p_max = 0
            best_c = INF
            best_p = -1
            for p in range(p_min, p_max + 1):
                base = dp[p][j - 1]
                if base == INF:
                    continue
                # Cost of cutting at gap before island p (when j > 1)
                cut_c = 0.0
                if j > 1:
                    g = gaps[p - 1]
                    if g < split_good:
                        cut_c = 2.6 * ((1.0 - g / max(0.05, split_good)) ** 2)
                # Cost of swallowing huge gaps inside [p .. i-1]
                int_c = big_pen[i - 1] - big_pen[p]
                # Duration match cost
                seg_dur = max(0.08, islands[i - 1][1] - islands[p][0])
                dur_c = 1.15 * abs(math.log(seg_dur / exp_dur))
                c = base + cut_c + int_c + dur_c
                if c < best_c:
                    best_c = c
                    best_p = p
            dp[i][j] = best_c
            prev_idx[i][j] = best_p

    spans = []
    i, j = k, n
    while j > 0:
        p = prev_idx[i][j]
        if p < 0:
            raise RuntimeError("DP partition failed to backtrack")
        spans.append((islands[p][0], islands[i - 1][1]))
        i, j = p, j - 1
    spans.reverse()
    return spans


def _process_clip(samples, sr, t0, t1, lo_lim, hi_lim):
    """Slice [t0, t1] with safe padding, click-free fades, and RMS normalization."""
    s0 = max(lo_lim, t0 - 0.045)
    s1 = min(hi_lim, t1 + 0.065)
    i0 = max(0, int(round(s0 * sr)))
    i1 = min(len(samples), int(round(s1 * sr)))
    if i1 <= i0:
        raise RuntimeError(f"Empty slice [{t0:.2f}, {t1:.2f}]")

    if _np is not None and isinstance(samples, _np.ndarray):
        seg = samples[i0:i1].astype(_np.float32, copy=True)
        pk = float(_np.max(_np.abs(seg))) if seg.size else 0.0
        if pk > 1e-5:
            voiced = seg[_np.abs(seg) > pk * 0.05]
            rms = float(_np.sqrt(_np.mean(voiced * voiced))) if voiced.size else pk * 0.3
            gain = min(0.15 / max(rms, 1e-4), 0.89 / pk, 6.0)
            seg *= gain
        n = seg.size
        fi = min(int(sr * 0.010), n // 4)
        fo = min(int(sr * 0.020), n // 4)
        if fi > 1:
            seg[:fi] *= 0.5 - 0.5 * _np.cos(_np.linspace(0.0, math.pi, fi, dtype=_np.float32))
        if fo > 1:
            seg[-fo:] *= 0.5 + 0.5 * _np.cos(_np.linspace(0.0, math.pi, fo, dtype=_np.float32))
        pcm = _np.clip(_np.round(seg * 32767.0), -32768, 32767).astype("<i2")
        return pcm.tobytes()

    seg = list(samples[i0:i1])
    pk = max((abs(x) for x in seg), default=0.0)
    if pk > 1e-5:
        voiced = [x * x for x in seg if abs(x) > pk * 0.05]
        rms = math.sqrt(sum(voiced) / len(voiced)) if voiced else pk * 0.3
        gain = min(0.15 / max(rms, 1e-4), 0.89 / pk, 6.0)
        seg = [x * gain for x in seg]
    n = len(seg)
    fi = min(int(sr * 0.010), n // 4)
    fo = min(int(sr * 0.020), n // 4)
    for k in range(fi):
        seg[k] *= 0.5 - 0.5 * math.cos(math.pi * k / max(1, fi - 1))
    for k in range(fo):
        seg[n - fo + k] *= 0.5 + 0.5 * math.cos(math.pi * k / max(1, fo - 1))
    out = array.array("h", [max(-32768, min(32767, int(round(x * 32767.0)))) for x in seg])
    if sys.byteorder != "little":
        out.byteswap()
    return out.tobytes()


def _write_take(pcm_bytes, sr, out_dir, vo_id, fmt="auto"):
    out_dir.mkdir(parents=True, exist_ok=True)
    ff = shutil.which("ffmpeg")
    use_ogg = (fmt == "ogg") or (fmt == "auto" and ff is not None)
    if use_ogg and not ff:
        print("[vo_batch] ffmpeg not found on PATH; falling back to .wav")
        use_ogg = False
    if not use_ogg:
        dst = out_dir / f"{vo_id}.wav"
        with wave.open(str(dst), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm_bytes)
        return dst
    dst = out_dir / f"{vo_id}.ogg"
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with wave.open(str(tmp_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm_bytes)
        subprocess.run(
            [ff, "-y", "-hide_banner", "-loglevel", "error",
             "-i", str(tmp_path), "-c:a", "libvorbis", "-q:a", "5", str(dst)],
            check=True,
        )
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
    return dst


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------
def cmd_status(args):
    voice._scan_files()
    total = len(VOICE_LINES)
    missing = _missing_lines()
    have = total - len(missing)
    by_group = {}
    for vo_id, sp, _tx in missing:
        gid = _group_for(vo_id, sp)
        by_group.setdefault(gid, []).append((vo_id, sp))

    print(f"Manifest lines : {total}")
    print(f"Recorded on disk: {have} ({have * 100.0 / max(1, total):.1f}%)")
    print(f"Missing audio   : {len(missing)}")
    print(f"KNOWN_MISSING   : {len(KNOWN_MISSING_AUDIO)}")
    stale = [vo for vo in KNOWN_MISSING_AUDIO if voice.has_file(vo)]
    if stale:
        print(f"Ready to sync   : {len(stale)} recorded ID(s) still in KNOWN_MISSING_AUDIO "
              f"(run: python tools/vo_batch.py sync-manifest)")
    if by_group:
        print("\nMissing by voice group (priority order):")
        for gid in sorted(by_group):
            folder, _ = _folder_and_style(gid)
            print(f"  {gid:<18} {len(by_group[gid]):3d} lines  -> assets/voice/{folder}/")


def cmd_make_refs(args):
    """Stitch ~25-30s clean reference WAVs from existing recordings per speaker."""
    out_dir = Path(args.out) / "refs"
    out_dir.mkdir(parents=True, exist_ok=True)
    voice._scan_files()
    by_speaker = {}
    for vo_id, sp, _tx in VOICE_LINES:
        if voice.has_file(vo_id):
            gid = _group_for(vo_id, sp)
            folder, _ = _folder_and_style(gid)
            by_speaker.setdefault(folder.upper(), []).append((vo_id, voice._files[vo_id]))

    target_s = float(args.seconds)
    built = 0
    for sp_name, items in sorted(by_speaker.items()):
        chunks = []
        ref_sr = None
        acc_s = 0.0
        used = 0
        for _vo, pth in items:
            try:
                samples, sr = _load_audio_mono(pth)
            except Exception:
                continue
            if ref_sr is None:
                ref_sr = sr
            elif sr != ref_sr:
                continue
            dur = len(samples) / float(sr)
            if dur < 0.8:
                continue
            pcm = _process_clip(samples, sr, 0.0, dur, 0.0, dur)
            chunks.append(pcm)
            chunks.append(b"\x00\x00" * int(sr * 0.35))
            acc_s += dur + 0.35
            used += 1
            if acc_s >= target_s:
                break
        if not chunks or ref_sr is None:
            continue
        dst = out_dir / f"{sp_name}_ref.wav"
        with wave.open(str(dst), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(ref_sr)
            w.writeframes(b"".join(chunks))
        print(f"  {dst.name:<22} {acc_s:5.1f}s  ({used} existing takes)")
        built += 1
    print(f"[vo_batch] Wrote {built} reference WAV(s) to {out_dir}")


def _build_existing_ref(gid, items):
    """Pick 1-2 clean existing recordings (~5-12s) + exact matching transcript."""
    scored = []
    for vo_id, pth, tx in items:
        if vo_id in BAKED_SCREAMS:
            continue
        clean_tx = _clean_for_tts(tx)
        if len(clean_tx) < 12:
            continue
        try:
            samples, sr = _load_audio_mono(pth)
        except Exception:
            continue
        dur = len(samples) / float(sr)
        if dur < 1.2 or dur > 14.0:
            continue
        scored.append((abs(dur - 6.0), dur, vo_id, samples, sr, clean_tx))
    if not scored:
        return None
    scored.sort(key=lambda r: r[0])
    chosen = []
    ref_sr = scored[0][4]
    acc_s = 0.0
    for _sc, dur, vo_id, samples, sr, clean_tx in scored:
        if sr != ref_sr:
            continue
        if chosen and acc_s + dur > 12.0:
            continue
        chosen.append((vo_id, samples, dur, clean_tx))
        acc_s += dur
        if acc_s >= 5.5 or len(chosen) >= 2:
            break
    chunks = []
    texts = []
    for idx, (_vo, samples, dur, clean_tx) in enumerate(chosen):
        env, dt = _rms_envelope(samples, ref_sr, hop_s=0.01)
        isl = _find_islands(env, dt, merge_gap_s=0.25)
        t0 = isl[0][0] if isl else 0.0
        t1 = isl[-1][1] if isl else dur
        chunks.append(_process_clip(samples, ref_sr, t0, t1, 0.0, dur))
        if idx < len(chosen) - 1:
            chunks.append(b"\x00\x00" * int(ref_sr * 0.28))
        texts.append(clean_tx)
    return b"".join(chunks), ref_sr, " ".join(texts), [c[0] for c in chosen]


def cmd_colab_pack(args):
    """Build build/vo_colab_kit.zip with existing refs + transcripts + missing lines."""
    out_zip = Path(args.out)
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    voice._scan_files()

    missing = _missing_lines()
    if args.redo_bodi:
        have = {r[0] for r in missing}
        bodi_old = [r for r in VOICE_LINES if r[1].upper() == "BODI" and r[0] not in have]
        missing = bodi_old + missing
    if not missing:
        print("[vo_batch] Nothing missing to pack for Colab.")
        return

    existing_by_group = {}
    for vo_id, sp, tx in VOICE_LINES:
        if voice.has_file(vo_id):
            gid = _group_for(vo_id, sp)
            existing_by_group.setdefault(gid, []).append((vo_id, voice._files[vo_id], tx))

    needed_groups = sorted({_group_for(vo, sp) for vo, sp, _ in missing})
    groups_meta = {}
    ref_wavs = {}

    for gid in needed_groups:
        folder, style = _folder_and_style(gid)
        ref = None
        if not (args.redo_bodi and gid == "06_BODI"):
            ref = _build_existing_ref(gid, existing_by_group.get(gid, []))
        if ref is not None:
            pcm, sr, ref_text, used_ids = ref
            ref_rel = f"refs/{gid}.wav"
            ref_wavs[ref_rel] = (pcm, sr)
            groups_meta[gid] = {
                "group_id": gid,
                "folder": folder,
                "mode": "clone_existing",
                "ref_wav": ref_rel,
                "ref_text": ref_text,
                "source_ids": used_ids,
            }
            print(f"  [CLONE ] {gid:<16} <- {', '.join(used_ids)} ({len(pcm) / (2 * sr):.1f}s)")
        else:
            anchor = DESIGN_ANCHORS.get(
                gid,
                "Stay low and keep moving through the rain. Nobody answers the radio tonight.",
            )
            groups_meta[gid] = {
                "group_id": gid,
                "folder": folder,
                "mode": "design",
                "instruct": style,
                "anchor_text": anchor,
            }
            print(f"  [DESIGN] {gid:<16} -> VoiceDesign -> {folder}/")

    jobs = []
    for vo_id, sp, tx in missing:
        gid = _group_for(vo_id, sp)
        folder, _ = _folder_and_style(gid)
        jobs.append({
            "vo_id": vo_id,
            "group_id": gid,
            "folder": folder,
            "speaker": sp,
            "text": tx,
            "tts_text": _clean_for_tts(tx),
            "units": voice._speech_units(tx),
        })

    payload = {"groups": groups_meta, "jobs": jobs}
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("jobs.json", json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        for rel, (pcm, sr) in ref_wavs.items():
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_p = Path(tmp.name)
            try:
                with wave.open(str(tmp_p), "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(sr)
                    w.writeframes(pcm)
                zf.write(tmp_p, rel)
            finally:
                try:
                    tmp_p.unlink()
                except OSError:
                    pass

    sz_mb = out_zip.stat().st_size / (1024 * 1024)
    print(f"\n[vo_batch] Packed {len(jobs)} lines ({len(ref_wavs)} existing voice refs, "
          f"{len(needed_groups) - len(ref_wavs)} VoiceDesign roles) -> {out_zip} ({sz_mb:.2f} MB)")
    print("Upload this zip + tools/vo_colab_qwen3.ipynb to https://colab.research.google.com")


def cmd_colab_import(args):
    """Import generated VO_xxx.wav takes from Colab's vo_generated.zip."""
    zpath = Path(args.zip_path)
    if not zpath.is_file():
        sys.exit(f"Zip file not found: {zpath}")
    by_id = {vo: (sp, tx) for vo, sp, tx in VOICE_LINES}
    voice._scan_files()

    installed = 0
    skipped = 0
    with tempfile.TemporaryDirectory() as tdir:
        with zipfile.ZipFile(zpath, "r") as zf:
            members = [m for m in zf.namelist() if Path(m).suffix.lower() in AUDIO_EXTS]
            for member in sorted(members):
                stem = Path(member).stem.upper()
                if stem not in by_id:
                    continue
                if not args.overwrite and voice.has_file(stem):
                    skipped += 1
                    continue
                extracted = Path(zf.extract(member, tdir))
                sp, _tx = by_id[stem]
                gid = _group_for(stem, sp)
                folder, _ = _folder_and_style(gid)
                samples, sr = _load_audio_mono(extracted)
                total_s = len(samples) / float(sr)
                env, dt = _rms_envelope(samples, sr, hop_s=0.01)
                islands = _find_islands(env, dt, merge_gap_s=0.25)
                t0 = islands[0][0] if islands else 0.0
                t1 = islands[-1][1] if islands else total_s
                pcm = _process_clip(samples, sr, t0, t1, 0.0, total_s)
                out_dir = _resolve_speaker_dir(folder)
                dst = _write_take(pcm, sr, out_dir, stem, fmt=args.format)
                voice._files[stem] = str(dst)
                installed += 1

    print(f"[vo_batch] Imported {installed} voice take(s) into assets/voice/ ({skipped} skipped).")
    if installed > 0 and not args.no_sync:
        cmd_sync_manifest(argparse.Namespace(dry_run=False))
    print("Next: python tools/build_radio_cache.py && python tools/voice_audit.py --check")


def cmd_ingest(args):
    """Auto-rename unrenamed AI Studio 'Generated Audio ...wav' drops by timestamp order."""
    src_dir = Path(args.folder)
    if not src_dir.is_dir():
        sys.exit(f"Drop folder not found: {src_dir}")

    needle = args.speaker.strip().upper()
    missing = _missing_lines()
    lines = [
        (vo, sp, tx) for vo, sp, tx in missing
        if sp.upper() == needle or needle in sp.upper() or needle in _group_for(vo, sp)
    ]
    if args.start:
        start_id = args.start.strip().upper()
        idx = next((i for i, r in enumerate(lines) if r[0] == start_id), None)
        if idx is None:
            sys.exit(f"Start ID '{start_id}' not found in missing lines for '{args.speaker}'.")
        lines = lines[idx:]
    if not lines:
        print(f"[vo_batch] No missing lines found for speaker '{args.speaker}'.")
        return

    files = [
        p for p in src_dir.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS
    ]
    if not files:
        print(f"[vo_batch] No audio files in {src_dir}.")
        return
    files.sort(key=lambda p: voice._file_order_key(str(p)))

    texts = {vo: tx for vo, _sp, tx in lines}
    by_id = {vo: (sp, tx) for vo, sp, tx in lines}
    durs = [voice._duration(str(p)) for p in files]

    if args.align or len(files) > len(lines):
        vo_ids = [vo for vo, _sp, _tx in lines]
        raw_pairs, extra, skipped_ids = voice._align(vo_ids, [str(p) for p in files], durs, texts)
        pairs = [(vo, Path(pth)) for vo, pth in raw_pairs]
        extra_paths = [Path(pth) for pth in extra]
    else:
        pairs = [(lines[i][0], files[i]) for i in range(len(files))]
        extra_paths = []
        skipped_ids = [vo for vo, _sp, _tx in lines[len(files):]]

    dur_map = dict(zip(files, durs))
    rates = sorted(
        (dur_map[p] or 0.0) / max(1.0, voice._speech_units(texts[vo]))
        for vo, p in pairs if dur_map.get(p)
    )
    med_rate = rates[len(rates) // 2] if rates else 0.068

    print(f"[ingest] {args.speaker.upper()}: {len(files)} file(s) -> {len(pairs)} matched "
          f"({len(lines) - len(pairs)} still remaining after this)")
    warns = 0
    written = 0
    done_dir = src_dir / "_done"

    for vo_id, fpath in pairs:
        sp, tx = by_id[vo_id]
        dur = dur_map.get(fpath) or 0.0
        exp = max(0.25, voice._speech_units(tx) * med_rate)
        ratio = dur / exp if dur > 0 else 0.0
        flag = "OK" if (0.42 <= ratio <= 2.40) else "CHECK"
        if flag != "OK":
            warns += 1
        print(f"  {vo_id}  <- {fpath.name:<48}  {dur:4.1f}s (exp ~{exp:4.1f}s) [{flag:5s}]  "
              f"{_clean_for_tts(tx)[:48]}")
        if args.dry_run:
            continue
        gid = _group_for(vo_id, sp)
        folder, _ = _folder_and_style(gid)
        samples, sr = _load_audio_mono(fpath)
        total_s = len(samples) / float(sr)
        env, dt = _rms_envelope(samples, sr, hop_s=0.01)
        isl = _find_islands(env, dt, merge_gap_s=0.25)
        t0 = isl[0][0] if isl else 0.0
        t1 = isl[-1][1] if isl else total_s
        pcm = _process_clip(samples, sr, t0, t1, 0.0, total_s)
        out_dir = _resolve_speaker_dir(folder)
        dst = _write_take(pcm, sr, out_dir, vo_id, fmt=args.format)
        voice._files[vo_id] = str(dst)
        written += 1
        if not args.keep:
            done_dir.mkdir(exist_ok=True)
            shutil.move(str(fpath), str(done_dir / f"{vo_id}__{fpath.name}"))

    if extra_paths:
        print("\nExtra/unmatched files (left untouched - retakes?):")
        for p in extra_paths:
            print(f"  {p.name}")
    if warns:
        print(f"\n[ingest] {warns} line(s) flagged CHECK - verify order before installing.")
    if not args.dry_run and written > 0:
        if not args.no_sync:
            cmd_sync_manifest(argparse.Namespace(dry_run=False))
        print(f"[ingest] Installed {written} take(s). Next: python tools/build_radio_cache.py")


def cmd_pack(args):
    out_dir = Path(args.out)
    scripts_dir = out_dir / "scripts"
    audio_dir = out_dir / "audio"
    missing = _missing_lines()
    if args.redo_bodi:
        have_ids = {r[0] for r in missing}
        bodi_old = [r for r in VOICE_LINES if r[1].upper() == "BODI" and r[0] not in have_ids]
        missing = bodi_old + missing
    if args.speaker:
        needle = args.speaker.upper()
        missing = [r for r in missing if needle in r[1].upper() or needle in _group_for(r[0], r[1])]
    if not missing:
        print("[vo_batch] Nothing missing to pack.")
        return

    grouped = {}
    for vo_id, sp, tx in missing:
        gid = _group_for(vo_id, sp)
        grouped.setdefault(gid, []).append((vo_id, sp, tx))

    scripts_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    # Clear old script txt files so stale batches don't confuse the user
    for old in scripts_dir.glob("*.txt"):
        old.unlink()

    batches = []
    for gid in sorted(grouped):
        folder, style = _folder_and_style(gid)
        chunks = _balanced_chunks(grouped[gid], max(1, int(args.batch_size)))
        for ci, chunk in enumerate(chunks, 1):
            batch_id = f"{gid}_{ci:02d}" if len(chunks) > 1 else gid
            lines_meta = [
                {
                    "vo_id": vo,
                    "speaker": sp,
                    "text": tx,
                    "tts_text": _clean_for_tts(tx),
                    "units": voice._speech_units(tx),
                }
                for vo, sp, tx in chunk
            ]
            batches.append({
                "batch_id": batch_id,
                "group_id": gid,
                "folder": folder,
                "style": style,
                "lines": lines_meta,
            })
            txt_lines = [
                f"BATCH: {batch_id}   ({len(chunk)} takes -> assets/voice/{folder}/)",
                f"SAVE DOWNLOADED WAV AS: {audio_dir.as_posix()}/{batch_id}.wav",
                "",
                "=== 1. STYLE INSTRUCTIONS (paste into AI Studio Style box) ===",
                f"{style} {PAUSE_RULE}",
                "",
                "=== 2. TEXT TO SPEAK (paste into AI Studio Text box) ===",
                "",
            ]
            for lm in lines_meta:
                txt_lines.append(lm["tts_text"])
                txt_lines.append("")
            txt_lines += [
                "=== REFERENCE (do NOT paste) ===",
            ]
            for idx, lm in enumerate(lines_meta, 1):
                txt_lines.append(f"  {idx:02d}. {lm['vo_id']} ({lm['speaker']}): {lm['tts_text']}")
            (scripts_dir / f"{batch_id}.txt").write_text(
                "\n".join(txt_lines) + "\n", encoding="utf-8", newline="\n"
            )

    meta_path = out_dir / "batches.json"
    meta_path.write_text(
        json.dumps({"batches": batches}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    readme = [
        "CALL OF ACARISTAN - AI STUDIO BATCH VO WORKFLOW",
        "===============================================",
        "",
        f"Packed {len(missing)} missing lines into {len(batches)} batches.",
        "",
        "1. Open a script in build/vo_batches/scripts/ (start at 01_...).",
        "2. In Google AI Studio (Single-Speaker Audio):",
        "   - Paste Section 1 into 'Style instructions'.",
        "   - Paste Section 2 into the text box.",
        "   - Pick the character's voice and click Run.",
        "3. Download the WAV and save it into build/vo_batches/audio/<BATCH_ID>.wav",
        "   (You can also drop single takes named VO_007.wav there.)",
        "4. Preview splits (no files written yet):",
        "   python tools/vo_batch.py split --dry-run",
        "5. Install takes into assets/voice/, update KNOWN_MISSING_AUDIO, build radio cache:",
        "   python tools/vo_batch.py split",
        "   python tools/vo_batch.py sync-manifest",
        "   python tools/build_radio_cache.py",
        "   python tools/voice_audit.py --check",
        "",
        "Tip: You can do 3-5 batches at a time and run steps 4-5 after each session.",
    ]
    (out_dir / "README_WORKFLOW.txt").write_text(
        "\n".join(readme) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"[vo_batch] Packed {len(missing)} lines into {len(batches)} scripts in {scripts_dir}")
    print(f"[vo_batch] Drop exported WAVs into: {audio_dir}")


def _split_one_batch(batch, audio_path, args):
    lines = batch["lines"]
    n = len(lines)
    samples, sr = _load_audio_mono(audio_path)
    total_s = len(samples) / float(sr)
    env, dt = _rms_envelope(samples, sr, hop_s=0.01)

    # Try requested merge gap, stepping finer only if fewer than N islands found
    islands = []
    used_gap = args.min_gap
    for gap in (args.min_gap, 0.12, 0.08, 0.05):
        if gap > args.min_gap:
            continue
        cand = _find_islands(env, dt, merge_gap_s=gap)
        islands = cand
        used_gap = gap
        if len(cand) >= n:
            break

    if len(islands) < n:
        print(f"[FAIL] {batch['batch_id']} ({audio_path.name}): found only {len(islands)} "
              f"speech islands for {n} lines (total {total_s:.1f}s).")
        for idx, (s, e) in enumerate(islands, 1):
            print(f"       island {idx:02d}: {s:6.2f}s - {e:6.2f}s ({e - s:.2f}s)")
        return 0, 1

    units = [lm["units"] for lm in lines]
    spans = _partition_islands_dp(islands, units)

    durs = [e - s for s, e in spans]
    ratios_base = sorted(d / max(1.0, u) for d, u in zip(durs, units))
    med_rate = ratios_base[len(ratios_base) // 2] if ratios_base else 0.065

    out_dir = _resolve_speaker_dir(batch["folder"])
    warns = 0
    written = 0
    print(f"\n[{batch['batch_id']}] {audio_path.name} ({total_s:.1f}s, "
          f"{len(islands)} islands -> {n} takes, gap={used_gap:.2f}s)")

    for i, (lm, (t0, t1)) in enumerate(zip(lines, spans)):
        vo_id = lm["vo_id"]
        dur = t1 - t0
        exp = max(0.2, lm["units"] * med_rate)
        ratio = dur / exp
        flag = "OK"
        if ratio < 0.42 or ratio > 2.40:
            flag = "CHECK"
            warns += 1
        print(f"  {vo_id}  [{t0:6.2f}s - {t1:6.2f}s]  {dur:4.2f}s "
              f"(exp ~{exp:4.2f}s)  [{flag:5s}]  {lm['tts_text'][:64]}")
        if args.dry_run:
            continue
        if not args.overwrite and voice.has_file(vo_id):
            continue
        lo_lim = 0.0 if i == 0 else (spans[i - 1][1] + t0) * 0.5
        hi_lim = total_s if i == n - 1 else (t1 + spans[i + 1][0]) * 0.5
        pcm = _process_clip(samples, sr, t0, t1, lo_lim, hi_lim)
        dst = _write_take(pcm, sr, out_dir, vo_id, fmt=args.format)
        voice._files[vo_id] = str(dst)
        written += 1

    if warns:
        print(f"  -> {warns} line(s) flagged CHECK: spot-listen to confirm timing.")
    elif not args.dry_run:
        print(f"  -> wrote {written} take(s) to {out_dir}")
    return written, warns


def _install_single_vo(vo_id, audio_path, args):
    by_id = {vo: (sp, tx) for vo, sp, tx in VOICE_LINES}
    if vo_id not in by_id:
        print(f"[SKIP] {audio_path.name}: {vo_id} is not in VOICE_LINES")
        return 0
    sp, tx = by_id[vo_id]
    gid = _group_for(vo_id, sp)
    folder, _ = _folder_and_style(gid)
    samples, sr = _load_audio_mono(audio_path)
    total_s = len(samples) / float(sr)
    env, dt = _rms_envelope(samples, sr, hop_s=0.01)
    islands = _find_islands(env, dt, merge_gap_s=0.25)
    t0 = islands[0][0] if islands else 0.0
    t1 = islands[-1][1] if islands else total_s
    out_dir = _resolve_speaker_dir(folder)
    print(f"[SINGLE] {vo_id} ({sp}) [{t0:.2f}s - {t1:.2f}s] ({t1 - t0:.2f}s) -> {out_dir.name}/")
    if args.dry_run:
        return 0
    if not args.overwrite and voice.has_file(vo_id):
        print(f"  (already exists; pass --overwrite to replace)")
        return 0
    pcm = _process_clip(samples, sr, t0, t1, 0.0, total_s)
    dst = _write_take(pcm, sr, out_dir, vo_id, fmt=args.format)
    voice._files[vo_id] = str(dst)
    return 1


def cmd_split(args):
    out_dir = Path(args.out)
    meta_path = out_dir / "batches.json"
    audio_dir = out_dir / "audio"
    voice._scan_files()

    batches_by_id = {}
    if meta_path.is_file():
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        batches_by_id = {b["batch_id"]: b for b in data.get("batches", [])}

    # Explicit --file + --batch mode (no need to rename downloaded WAV)
    if args.file:
        fpath = Path(args.file)
        if not fpath.is_file():
            sys.exit(f"Audio file not found: {fpath}")
        if args.batch:
            if args.batch not in batches_by_id:
                sys.exit(f"Unknown batch ID '{args.batch}'. Run pack first.")
            _split_one_batch(batches_by_id[args.batch], fpath, args)
            return
        m = re.match(r"^(VO_\d+)$", fpath.stem, re.I)
        if m:
            _install_single_vo(m.group(1).upper(), fpath, args)
            return
        sys.exit("Pass --batch <BATCH_ID> when using --file with an unrenamed audio file.")

    if not audio_dir.is_dir():
        sys.exit(f"Audio drop folder not found: {audio_dir} (run pack first)")

    total_written = 0
    total_warns = 0
    matched = 0
    for fpath in sorted(audio_dir.iterdir()):
        if not fpath.is_file() or fpath.suffix.lower() not in AUDIO_EXTS:
            continue
        stem = fpath.stem
        if args.batch and stem != args.batch:
            continue
        if stem in batches_by_id:
            matched += 1
            w, wrn = _split_one_batch(batches_by_id[stem], fpath, args)
            total_written += w
            total_warns += wrn
        elif re.match(r"^VO_\d+$", stem, re.I):
            matched += 1
            total_written += _install_single_vo(stem.upper(), fpath, args)
        else:
            print(f"[SKIP] {fpath.name}: stem '{stem}' does not match any batch ID or VO_xxx")

    if matched == 0:
        print(f"[vo_batch] No matching audio files in {audio_dir}.")
        return
    mode = "DRY RUN" if args.dry_run else f"DONE (wrote {total_written} takes)"
    print(f"\n[vo_batch] {mode} across {matched} file(s); {total_warns} warning(s).")
    if not args.dry_run and total_written > 0:
        print("Next: python tools/vo_batch.py sync-manifest && python tools/build_radio_cache.py")


def cmd_sync_manifest(args):
    voice.rescan()
    voice._scan_files()
    found = {vo for vo in KNOWN_MISSING_AUDIO if voice.has_file(vo)}
    if not found:
        print("[vo_batch] KNOWN_MISSING_AUDIO is already in sync with assets/voice/.")
        return

    src = MANIFEST_PATH.read_text(encoding="utf-8")
    m = re.search(
        r"(KNOWN_MISSING_AUDIO\s*=\s*frozenset\(\{\s*\n)(.*?)(\n\}\))",
        src,
        re.S,
    )
    if not m:
        sys.exit("Could not locate KNOWN_MISSING_AUDIO block in voice_manifest.py")

    body = m.group(2)
    out_lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out_lines.append(line)
            continue
        ids = re.findall(r"['\"](VO_\d+)['\"]", line)
        if not ids:
            out_lines.append(line)
            continue
        kept = [vo for vo in ids if vo not in found]
        if not kept:
            continue
        indent = line[:len(line) - len(line.lstrip())]
        out_lines.append(indent + ", ".join(f"'{vo}'" for vo in kept) + ",")

    new_src = src[:m.start(2)] + "\n".join(out_lines) + src[m.end(2):]
    # Verify valid Python syntax before touching disk
    ast.parse(new_src)
    print(f"[vo_batch] Removing {len(found)} recorded ID(s) from KNOWN_MISSING_AUDIO "
          f"({len(KNOWN_MISSING_AUDIO) - len(found)} remaining).")
    if args.dry_run:
        print("  (dry run: no file written)")
        return
    MANIFEST_PATH.write_text(new_src, encoding="utf-8", newline="\n")
    print(f"[vo_batch] Updated {MANIFEST_PATH.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser(description="Batch VO packer & splitter for Call of Acaristan")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_st = sub.add_parser("status", help="Show recorded vs missing VO counts by voice group")
    p_st.set_defaults(fn=cmd_status)

    p_rf = sub.add_parser("make-refs", help="Stitch ~25-30s voice reference WAVs from existing takes")
    p_rf.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory")
    p_rf.add_argument("--seconds", type=float, default=28.0, help="Target clip length in seconds")
    p_rf.set_defaults(fn=cmd_make_refs)

    p_pk = sub.add_parser("pack", help="Generate copy-paste AI Studio batch scripts")
    p_pk.add_argument("--batch-size", type=int, default=12, help="Max lines per batch (default 12)")
    p_pk.add_argument("--speaker", default=None, help="Filter by speaker/group substring")
    p_pk.add_argument("--redo-bodi", action="store_true", help="Include Bodi's 5 old lines for a fresh consistent voice")
    p_pk.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory")
    p_pk.set_defaults(fn=cmd_pack)

    p_sp = sub.add_parser("split", help="Split downloaded batch WAVs into assets/voice/")
    p_sp.add_argument("--out", default=str(DEFAULT_OUT), help="Batch directory")
    p_sp.add_argument("--batch", default=None, help="Process only this batch ID")
    p_sp.add_argument("--file", default=None, help="Specific audio file (pair with --batch)")
    p_sp.add_argument("--dry-run", action="store_true", help="Print split timestamps without writing")
    p_sp.add_argument("--overwrite", action="store_true", help="Overwrite existing VO_xxx takes")
    p_sp.add_argument("--format", choices=("auto", "ogg", "wav"), default="auto",
                      help="Output format (auto: .ogg if ffmpeg is on PATH, else .wav)")
    p_sp.add_argument("--min-gap", type=float, default=0.18,
                      help="Micro-gap merge threshold in seconds (default 0.18)")
    p_sp.set_defaults(fn=cmd_split)

    p_sy = sub.add_parser("sync-manifest", help="Remove recorded IDs from KNOWN_MISSING_AUDIO")
    p_sy.add_argument("--dry-run", action="store_true", help="Preview count without editing")
    p_sy.set_defaults(fn=cmd_sync_manifest)

    p_cp = sub.add_parser("colab-pack", help="Build vo_colab_kit.zip for Google Colab Qwen3-TTS")
    p_cp.add_argument("--out", default=str(ROOT / "build" / "vo_colab_kit.zip"),
                      help="Output zip path")
    p_cp.add_argument("--redo-bodi", action="store_true",
                      help="Design a fresh Bodi voice & re-generate all Bodi lines")
    p_cp.set_defaults(fn=cmd_colab_pack)

    p_ci = sub.add_parser("colab-import", help="Import vo_generated.zip from Colab into assets/voice/")
    p_ci.add_argument("zip_path", help="Path to downloaded vo_generated.zip")
    p_ci.add_argument("--format", choices=("auto", "ogg", "wav"), default="auto",
                      help="Output format (auto: .ogg if ffmpeg on PATH, else .wav)")
    p_ci.add_argument("--overwrite", action="store_true", help="Replace existing VO_xxx takes")
    p_ci.add_argument("--no-sync", action="store_true", help="Do not auto-update KNOWN_MISSING_AUDIO")
    p_ci.set_defaults(fn=cmd_colab_import)

    p_in = sub.add_parser("ingest", help="Auto-rename unrenamed AI Studio drops by timestamp order")
    p_in.add_argument("speaker", help="Speaker or group name (e.g. NARRATOR, MARU, BODI, VASILE)")
    p_in.add_argument("folder", help="Folder containing unrenamed 'Generated Audio ...wav' files")
    p_in.add_argument("--start", default=None, help="Start at a specific VO_xxx ID")
    p_in.add_argument("--align", action="store_true", help="Use length-DP alignment (if you skipped lines or have retakes)")
    p_in.add_argument("--dry-run", action="store_true", help="Preview filename -> VO_xxx mapping without moving/writing")
    p_in.add_argument("--keep", action="store_true", help="Do not move consumed files into _done/")
    p_in.add_argument("--format", choices=("auto", "ogg", "wav"), default="auto",
                      help="Output format (auto: .ogg if ffmpeg on PATH, else .wav)")
    p_in.add_argument("--no-sync", action="store_true", help="Do not auto-update KNOWN_MISSING_AUDIO")
    p_in.set_defaults(fn=cmd_ingest)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
