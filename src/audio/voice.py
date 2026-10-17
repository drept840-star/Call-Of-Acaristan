"""Voice-over playback for Call of Acaristan.

Drop recorded lines into ``assets/voice/`` named by their spreadsheet ID
(``VO_001.ogg`` / ``.wav`` / ``.mp3`` - sub-folders per speaker are fine,
e.g. ``assets/voice/VASILE/VO_012.ogg``). Lines with no file simply stay
silent text, so you can record the game a few lines at a time.

Two delivery modes, chosen by WHERE the line is heard - not by who says it:

  * radio=True  - in-game radio transmissions (core.interactions radio
                  director), cutscene shots tagged ``"radio": True``, PA/
                  dispatch speakers, and Balaceanu's taped monitor lines.
                  The clean recording is run through a radio chain
                  (telephone band-pass, saturation, light crush, hiss and a
                  squelch in/out) at load time.
  * radio=False - everything said in person (cutscenes, interrogation,
                  the Maru meet): played exactly as recorded.

So the SAME actor file is reused - Vasile in the van is clean, Vasile on
channel 4 is radio. Record everything clean; never bake the effect in.

Processed radio versions are cached to ``assets/voice/_radio_cache/`` so the
(pure-Python, numpy-free) filter only runs once per line, ever.
"""
import array
import hashlib
import io
import math
import os
import random
import re
import struct

import pygame
from engine.assets import load_sound as _load_sound  # RPE6 D5: raw loads via engine.assets

from audio.voice_manifest import VOICE_LINES, VOICE_ORDER

# Speakers whose lines are always "through a speaker" even outside the radio
# director (PA / dispatch / broadcast voices).
ALWAYS_RADIO_SPEAKERS = ("(PA)", "PA SYSTEM", "IPA DISPATCH")

# Overall VO level relative to SFX (master * sfx volume). Voice should sit on
# top of the mix, so it ignores per-sound attenuation and plays at full scale.
VOICE_GAIN = 1.0
# Radio static under a voiced transmission (core.interactions) - kept low so
# it colours the line instead of masking it.
RADIO_STATIC_UNDER_VO = 0.12

_EXTS = (".ogg", ".wav", ".mp3", ".flac")
# Radio FX padding added around a processed clip (seconds): noise burst in,
# key-up click + static tail out. Shared by _radio_samples and _clip_ms.
RADIO_SQUELCH_IN_S = 0.07
RADIO_SQUELCH_OUT_S = 0.16
_files = None            # VO_ID -> path, built lazily by scanning the folder
_clean = {}              # VO_ID -> Sound
_radio = {}              # VO_ID -> Sound
_channel = None
_index = None            # normalized text -> [(vo_id, speaker), ...]
_deaths = {}             # character (lower) -> path of their death scream
_extra = []              # channels playing death screams (stopped/paused with VO)
_paused = False
_onsets = {}             # VO_ID -> seconds where a scream baked into the clip starts
_DEATH_WORDS = ("death", "scream", "dies", "die_")


def _voice_dir():
    try:
        from core.config import resource_path
        return resource_path(os.path.join("assets", "voice"))
    except Exception:
        return os.path.join(os.path.abspath("."), "assets", "voice")


_PREFIX = re.compile(r'^\s*([A-Z][A-Z0-9 .\-()/]+?):\s*')


def _norm(text):
    """Speaker-prefix-free, punctuation/whitespace-free lowercase key, so
    'VASILE: "Biribel, move."', the cutscene's 'Biribel,\\nmove.' and the
    spreadsheet's 'Biribel, / move.' all map to the same entry."""
    if not text:
        return ""
    text = _PREFIX.sub("", text, count=1)
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _split_speaker(text):
    m = _PREFIX.match(text or "")
    return (m.group(1).strip(), text[m.end():]) if m else ("", text or "")


def _build_index():
    global _index
    _index = {}
    for vo_id, speaker, text in VOICE_LINES:
        _index.setdefault(_norm(text), []).append((vo_id, speaker.upper()))


def find_line(speaker, text):
    """Spreadsheet ID for a spoken line, or None."""
    if _index is None:
        _build_index()
    hits = _index.get(_norm(text))
    if not hits:
        return None
    if len(hits) > 1 and speaker:
        sp = speaker.upper()
        for vo_id, s in hits:
            if s == sp or s in sp or sp in s:
                return vo_id
    return hits[0][0]


_VO_NAME = re.compile(r"^VO_\d+$", re.I)
_STAMP = re.compile(
    r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\D+?(\d{1,2})[_.:](\d{2})(?:[_.:](\d{2}))?\s*([AP]M)?",
    re.I)
_MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"), 1)}


def _file_order_key(path):
    """Oldest-first sort key for unrenamed TTS exports.

    Uses the timestamp printed in the file NAME first ("Generated Audio
    October 07, 2026 - 9_33_05 PM.wav"), because copying files between
    drives can reset 'date modified'. Falls back to the file's modified
    time, then the name, for ties and for names without a timestamp.
    """
    name = os.path.basename(path)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0.0
    m = _STAMP.search(name)
    stamp = None
    if m and m.group(1).lower() in _MONTHS:
        mon = _MONTHS[m.group(1).lower()]
        day, year = int(m.group(2)), int(m.group(3))
        hh, mm = int(m.group(4)), int(m.group(5))
        ss = int(m.group(6) or 0)
        ampm = (m.group(7) or "").upper()
        if ampm == "PM" and hh != 12:
            hh += 12
        elif ampm == "AM" and hh == 12:
            hh = 0
        stamp = (year, mon, day, hh, mm, ss)
    # Named-stamp files sort by stamp; within the same stamp (exports with
    # no seconds) by modified time; stamp-less files go by modified time.
    # Windows names same-minute exports "... 9_33 PM.wav", "... 9_33 PM (1).wav",
    # "(2)" ... - the copy number is the real order there, and must sort
    # numerically ("(10)" after "(9)"), with the un-numbered file first.
    cm = re.search(r"\((\d+)\)\s*$", os.path.splitext(name)[0])
    copy_n = int(cm.group(1)) if cm else 0
    return (0, stamp, copy_n, mtime, name) if stamp else (1, (), copy_n, mtime, name)


def _scan_files():
    global _files
    _files = {}
    root = _voice_dir()
    if not os.path.isdir(root):
        return
    unnamed = {}          # speaker folder (upper) -> [paths]
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != "_radio_cache")
        if os.path.basename(dirpath) == "_radio_cache":
            continue
        recordings = {}
        for fn in sorted(filenames):
            stem, ext = os.path.splitext(fn)
            ext = ext.lower()
            if ext not in _EXTS:
                continue
            key = stem.casefold()
            if key not in recordings or _EXTS.index(ext) < _EXTS.index(recordings[key][1]):
                recordings[key] = (fn, ext)
        # WAV and OGG exports of the same take must occupy one dialogue slot.
        for fn, _ext in recordings.values():
            stem = os.path.splitext(fn)[0]
            path = os.path.join(dirpath, fn)
            low = stem.lower() + "_" + os.path.basename(dirpath).lower()
            if any(w in low for w in _DEATH_WORDS):
                # death screams are cues, not lines: never let them into the
                # length alignment below (they'd steal a line's slot)
                for who in ("gabi", "seby", "sebi", "darius", "biribel", "vasile"):
                    if who in low:
                        _deaths.setdefault("seby" if who == "sebi" else who, path)
                        break
                continue
            if _VO_NAME.match(stem):
                _files.setdefault(stem.upper(), path)      # explicit name wins
            elif os.path.abspath(dirpath) != os.path.abspath(root):
                folder = os.path.basename(dirpath).upper()
                unnamed.setdefault(folder, []).append(path)

    # Unrenamed files in a speaker folder (assets/voice/Vasile/...): match
    # them to that speaker's lines in spreadsheet order, oldest file first -
    # but ALIGNED BY LENGTH, not blindly 1:1. One skipped line or one extra
    # retake used to shift every later line by one (the "Seven seconds"
    # line playing at the start of Mission 2). _align() lines the clips up
    # against the expected length of each line, so an extra take is dropped
    # and a missing line is left silent instead of breaking the rest.
    # Explicitly named VO_xxx files always win.
    for folder, paths in unnamed.items():
        order = VOICE_ORDER.get(folder)
        if not order:
            print(f"[voice] folder '{folder}' doesn't match a speaker tab - "
                  f"files there are ignored unless named VO_xxx")
            continue
        paths.sort(key=_file_order_key)
        free = [vo for vo in order if vo not in _files]
        texts = {vo: t for vo, _sp, t in VOICE_LINES}
        durs = [_duration(pth) for pth in paths]
        pairs, extra, missing = _align(free, paths, durs, texts)
        for vo_id, pth in pairs:
            _files[vo_id] = pth
        print(f"[voice] {folder}: {len(paths)} files -> {len(pairs)} of {len(free)} "
              f"lines matched; {len(extra)} extra file(s), {len(missing)} line(s) "
              f"without audio - see {folder.lower()}_matches.txt")
        try:
            by_line = dict(pairs)
            dmap = dict(zip(paths, durs))
            with open(os.path.join(root, f"{folder.lower()}_matches.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("LINE\tFILE\tSECONDS\tTEXT\n")
                for vo_id in free:
                    pth = by_line.get(vo_id)
                    if pth:
                        fh.write(f"{vo_id}\t{os.path.basename(pth)}\t"
                                 f"{dmap.get(pth) or 0:.1f}\t{texts.get(vo_id, '')}\n")
                    else:
                        fh.write(f"{vo_id}\t(NO AUDIO - record & name it {vo_id}.wav)"
                                 f"\t\t{texts.get(vo_id, '')}\n")
                if extra:
                    fh.write("\nEXTRA FILES (not used - retakes/duplicates?):\n")
                    for pth in extra:
                        fh.write(f"\t{os.path.basename(pth)}\t{dmap.get(pth) or 0:.1f}\n")
        except OSError:
            pass


def _ogg_frames(path):
    """(total samples, sample rate) of an Ogg Vorbis file from the container
    alone (no decode): rate from the identification header, samples from the
    last page's granule position. None for anything that is not plain Vorbis."""
    import struct
    with open(path, "rb") as fh:
        head = fh.read(128)
        if head[:4] != b"OggS":
            return None
        i = head.find(b"\x01vorbis")
        if i < 0 or i + 16 > len(head):
            return None
        rate = struct.unpack_from("<I", head, i + 12)[0]
        if rate <= 0:
            return None
        fh.seek(0, 2)
        size = fh.tell()
        fh.seek(max(0, size - 65536))
        tail = fh.read()
    j = tail.rfind(b"OggS")
    if j < 0 or j + 14 > len(tail):
        return None
    granule = struct.unpack_from("<q", tail, j + 6)[0]
    return (granule, rate) if granule > 0 else None


def _source_frames(path):
    """(frames, sample rate) from the file header: WAV or Ogg Vorbis, else None."""
    try:
        import wave
        with wave.open(path, "rb") as w:
            return w.getnframes(), w.getframerate()
    except Exception:
        pass
    try:
        return _ogg_frames(path)
    except Exception:
        return None


def _duration(path):
    """Clip length in seconds (cheap header read for WAV/OGG, else decode)."""
    nf = _source_frames(path) if path else None
    if nf:
        return nf[0] / float(nf[1])
    try:
        return _load_sound(path).get_length()
    except Exception:
        return None


def _speech_units(text):
    """Rough 'how long should this take' measure: letters plus a pause
    allowance for every line break / sentence end."""
    t = text or ""
    letters = len(re.sub(r"[^A-Za-z0-9]", "", t))
    pauses = len(re.findall(r"[.!?]+|\s/\s|\n|\u2026|--| - ", t))
    return letters + 6.0 * pauses + 4.0


def _align(lines, paths, durs, texts, skip_file=0.5, skip_line=0.5):
    """Order-preserving alignment of clips to lines (edit-distance DP).

    Matching costs |ln(actual / expected)|; skipping a file (extra take) or
    a line (not recorded) costs a fixed penalty. The speaking rate is fitted
    from the data, then refined once from the first pass's matches.
    Returns (pairs, extra_paths, missing_lines).
    """
    n, m = len(paths), len(lines)
    units = [_speech_units(texts.get(vo, "")) for vo in lines]
    if not n or not m or any(d is None or d <= 0 for d in durs):
        pairs = list(zip(lines, paths))           # can't measure: plain 1:1
        return pairs, list(paths[m:]), list(lines[n:])

    def run(rate):
        INF = float("inf")
        cost = [[INF] * (m + 1) for _ in range(n + 1)]
        back = [[None] * (m + 1) for _ in range(n + 1)]
        cost[0][0] = 0.0
        for i in range(n + 1):
            for j in range(m + 1):
                c = cost[i][j]
                if c == INF:
                    continue
                if i < n and j < m:
                    mc = c + abs(math.log(durs[i] / (units[j] * rate)))
                    if mc < cost[i + 1][j + 1]:
                        cost[i + 1][j + 1] = mc; back[i + 1][j + 1] = "M"
                if i < n:
                    sc = c + skip_file
                    if sc < cost[i + 1][j]:
                        cost[i + 1][j] = sc; back[i + 1][j] = "F"
                if j < m:
                    lc = c + skip_line
                    if lc < cost[i][j + 1]:
                        cost[i][j + 1] = lc; back[i][j + 1] = "L"
        i, j, pairs, extra, missing = n, m, [], [], []
        while i or j:
            step = back[i][j]
            if step == "M":
                i -= 1; j -= 1; pairs.append((lines[j], paths[i]))
            elif step == "F":
                i -= 1; extra.append(paths[i])
            else:
                j -= 1; missing.append(lines[j])
        pairs.reverse(); extra.reverse(); missing.reverse()
        return pairs, extra, missing

    rate = sum(durs) / max(1.0, sum(units))
    pairs, extra, missing = run(rate)
    if pairs:
        idx = {p: k for k, p in enumerate(paths)}
        jdx = {vo: k for k, vo in enumerate(lines)}
        ratios = sorted(durs[idx[p]] / units[jdx[vo]] for vo, p in pairs)
        rate = ratios[len(ratios) // 2]
        pairs, extra, missing = run(rate)
    return pairs, extra, missing


def has_file(vo_id):
    if _files is None:
        _scan_files()
    return vo_id in _files


# ─────────────────────────────────────────────
# Radio chain (pure Python on the mixer's own sample format)
# ─────────────────────────────────────────────
def _radio_seed(vo_id):
    """Stable per-clip noise seed (no hash(): PYTHONHASHSEED must not matter)."""
    return sum((i + 1) * ord(c) for i, c in enumerate(str(vo_id))) + 73_000


def _radio_samples(raw, rate, chans, seed=0):
    """Return processed interleaved int16 samples for a clean recording.

    ``seed`` drives the hiss/squelch noise. It is derived from the clip id so
    the processed clip (and its on-disk cache) is identical on every machine
    and the shared game RNG is never consumed here (RPE6 B-012).
    """
    src = array.array("h")
    src.frombytes(raw)
    n = len(src) // chans
    if chans == 2:
        mono = [(src[2 * i] + src[2 * i + 1]) * 0.5 for i in range(n)]
    else:
        mono = [float(v) for v in src[:n]]

    def lp(buf, hz):
        a = 1.0 - math.exp(-2.0 * math.pi * hz / rate)
        p = 0.0
        for i in range(len(buf)):
            p += a * (buf[i] - p)
            buf[i] = p

    def hp(buf, hz):
        a = math.exp(-2.0 * math.pi * hz / rate)
        px = py = 0.0
        for i in range(len(buf)):
            x = buf[i]
            py = a * (py + x - px)
            px = x
            buf[i] = py

    # Telephone/handset band: ~350 Hz - 3.2 kHz, two poles each side.
    hp(mono, 350.0); hp(mono, 350.0)
    lp(mono, 3200.0); lp(mono, 3200.0)

    # Level by the SPEECH loudness, not the single loudest sample: TTS
    # exports often start with a click or breath spike, and peak-normalising
    # to that left the actual words far too quiet. Gate out near-silence,
    # take the RMS of what's left, and drive it to a hot, consistent level.
    peak = max((abs(v) for v in mono), default=0.0) or 1.0
    gate = peak * 0.05
    voiced = [v * v for v in mono if abs(v) > gate]
    rms = math.sqrt(sum(voiced) / len(voiced)) if voiced else peak * 0.3
    drive = min(0.85 / max(rms, 1.0), 6.0 / peak)   # ~speech RMS -> 0.85 pre-clip
    crush = 1.0 / 2048.0                     # ~11-bit grit
    tanh = math.tanh
    rnd = random.Random(seed).random   # private stream: not the legacy game RNG (B-012)
    out = [0.0] * n
    for i in range(n):
        y = tanh(mono[i] * drive)
        y = round(y / crush) * crush
        out[i] = y * 0.80 + (rnd() * 2.0 - 1.0) * 0.018   # carrier hiss

    # Squelch: short noise burst in, key-up click + static tail out.
    sq_in = int(rate * RADIO_SQUELCH_IN_S)
    sq_out = int(rate * RADIO_SQUELCH_OUT_S)
    burst = [(rnd() * 2.0 - 1.0) * 0.30 * (1.0 - k / sq_in) for k in range(sq_in)]
    tail = [(rnd() * 2.0 - 1.0) * 0.22 * (1.0 - k / sq_out) ** 2 for k in range(sq_out)]
    if tail:
        tail[0] = 0.85
        if len(tail) > 1:
            tail[1] = -0.6
    lp(burst, 2600.0); lp(tail, 2600.0)
    seq = burst + out + tail

    res = array.array("h", [0]) * (len(seq) * chans)
    for i, v in enumerate(seq):
        s = int(max(-1.0, min(1.0, v)) * 32000)
        if chans == 2:
            res[2 * i] = s
            res[2 * i + 1] = s
        else:
            res[i] = s
    return res


def _wav_bytes(samples, rate, chans):
    data = samples.tobytes()
    b = io.BytesIO()
    b.write(b"RIFF"); b.write(struct.pack("<I", 36 + len(data))); b.write(b"WAVE")
    b.write(b"fmt "); b.write(struct.pack("<IHHIIHH", 16, 1, chans, rate,
                                          rate * chans * 2, chans * 2, 16))
    b.write(b"data"); b.write(struct.pack("<I", len(data))); b.write(data)
    return b.getvalue()


def _load(vo_id, radio):
    cache = _radio if radio else _clean
    if vo_id in cache:
        return cache[vo_id]
    snd = None
    try:
        path = _files.get(vo_id)
        if path:
            clean = _clean.get(vo_id) or _load_sound(path)
            _clean[vo_id] = clean
            if not radio:
                snd = clean
            else:
                rate, size, chans = pygame.mixer.get_init()
                if abs(size) != 16:
                    raise RuntimeError("radio FX expects a 16-bit mixer")
                raw = clean.get_raw()
                digest = hashlib.sha256(raw)
                digest.update(repr((rate, size, chans, RADIO_SQUELCH_IN_S,
                                    RADIO_SQUELCH_OUT_S)).encode("ascii"))
                cdir = os.path.join(_voice_dir(), "_radio_cache")
                cpath = os.path.join(cdir, vo_id + "_" + digest.hexdigest()[:16] + ".wav")
                if os.path.exists(cpath):
                    snd = _load_sound(cpath)
                else:
                    wav = _wav_bytes(_radio_samples(raw, rate, chans,
                                                    seed=_radio_seed(vo_id)),
                                     rate, chans)
                    snd = _load_sound(io.BytesIO(wav))
                    try:
                        os.makedirs(cdir, exist_ok=True)
                        with open(cpath, "wb") as fh:
                            fh.write(wav)
                    except OSError:
                        pass    # read-only install: keep the in-memory copy
    except Exception as exc:
        print(f"[voice] could not load {vo_id}: {exc}")
        snd = None
    cache[vo_id] = snd
    return snd


def _clip_ms(vo_id, radio, snd):
    """Playback length in ms for subtitles/ducking.

    Computed from the source file's header (frames + rate, WAV or Ogg) the way
    SDL sizes a decoded WAV - ``floor(frames * mixer_rate / source_rate)``
    samples, plus the radio squelch padding - instead of ``snd.get_length()``.
    Reason: SDL's decoded length of a Vorbis clip is ~12-33 ms short (resampler
    flush), which cut voiced subtitles early after the WAV -> OGG conversion.
    This reproduces the WAV-era value to the millisecond (loop oracle m1-m5
    bit-identical to the pre-conversion baseline).
    """
    init = pygame.mixer.get_init()
    rate = init[0] if init else 22050
    nf = None
    try:
        nf = _source_frames((_files or {}).get(vo_id))
    except Exception:
        nf = None
    if not nf:
        return int(snd.get_length() * 1000)
    n = (nf[0] * rate) // nf[1]
    if radio:
        n += int(rate * RADIO_SQUELCH_IN_S) + int(rate * RADIO_SQUELCH_OUT_S)
    return int(n / float(rate) * 1000)


def _effective_volume():
    try:
        from core.config import audio
        return max(0.0, min(1.0, audio.master_volume * audio.sfx_volume))
    except Exception:
        return 1.0


def play_line(speaker, text, radio=False, volume=1.0):
    """Play the recorded VO for a line, if one exists.

    ``text`` may still carry a 'SPEAKER: "..."' radio prefix. Returns the
    clip length in ms (0 when nothing was played), so callers like the radio
    director can hold the channel until the actor finishes.
    """
    global _channel
    if not text:
        return 0
    if not pygame.mixer.get_init():
        return 0
    pre_speaker, _ = _split_speaker(text)
    speaker = speaker or pre_speaker
    vo_id = find_line(speaker, text)
    if not vo_id or not has_file(vo_id):
        return 0
    sp = (speaker or "").upper()
    if any(tag in sp for tag in ALWAYS_RADIO_SPEAKERS):
        radio = True
    snd = _load(vo_id, radio)
    if snd is None:
        return 0
    try:
        from audio.audio import VOICE_CHANNEL_INDEX
        if pygame.mixer.get_num_channels() <= VOICE_CHANNEL_INDEX:
            pygame.mixer.set_num_channels(VOICE_CHANNEL_INDEX + 1)
        pygame.mixer.set_reserved(VOICE_CHANNEL_INDEX + 1)   # idempotent
        _channel = pygame.mixer.Channel(VOICE_CHANNEL_INDEX)
        _channel.stop()
        # Channel volume persists between sounds in pygame, so always reset
        # it - a stale low value is exactly what made radio VO whisper-quiet.
        _channel.set_volume(1.0)
        snd.set_volume(min(1.0, _effective_volume() * volume * VOICE_GAIN))
        _channel.play(snd)
    except Exception as exc:
        print(f"[voice] play failed for {vo_id}: {exc}")
        return 0
    ms = _clip_ms(vo_id, radio, snd)
    try:
        from core.config import audio
        audio.duck_for_radio(frames=int(ms / 1000 * 60) + 10, factor=0.45)
    except Exception:
        pass
    return ms


def clip_ms(speaker, text):
    """Length in ms of the recorded clip for a line (0 when unrecorded).

    Header-only read, no mixer needed: the radio director and the voice
    audit (tools/voice_audit.py) size subtitles from this."""
    pre_speaker, _ = _split_speaker(text or "")
    vo_id = find_line(speaker or pre_speaker, text)
    if not vo_id or not has_file(vo_id):
        return 0
    d = _duration(_files[vo_id])
    return int(d * 1000) if d else 0


def fade_out(ms=120):
    """Fade the current line out over ``ms`` (a cutscene cutting in on a
    live radio line). Death screams are cut, they never overlap a cut."""
    global _paused
    _paused = False
    if _channel is not None:
        try:
            if _channel.get_busy():
                _channel.fadeout(max(1, int(ms)))
        except Exception:
            pass


def busy():
    try:
        return bool(_channel is not None and _channel.get_busy())
    except Exception:
        return False


def stop():
    """Cut the current line and any death scream immediately."""
    global _paused
    _paused = False
    for ch in [_channel] + _extra:
        if ch is not None:
            try:
                ch.stop()
            except Exception:
                pass
    _extra.clear()


def pause():
    """Freeze VO + screams (pause menu) so they don't run ahead of the scene."""
    global _paused
    _paused = True
    for ch in [_channel] + _extra:
        if ch is not None:
            try:
                ch.pause()
            except Exception:
                pass


def resume():
    global _paused
    if not _paused:
        return
    _paused = False
    for ch in [_channel] + _extra:
        if ch is not None:
            try:
                ch.unpause()
            except Exception:
                pass


# ─────────────────────────────────────────────
# Death screams
# ─────────────────────────────────────────────
# Two ways to add them:
#   1. Separate file (recommended): assets/voice/death/gabi.wav, seby.wav,
#      darius.wav (any name containing the character + "death" or "scream"
#      works, e.g. Gabi_Scream.wav). It plays on the exact frame the round
#      hits.
#   2. Scream recorded onto the END of the line itself (VO_110 "Vasile, I
#      have-"). The game finds where the scream starts and fires the shot
#      there, so the scream is the reaction instead of a warning. If the
#      guess is off, pin it in voice_manifest.DEATH_AT (seconds into clip).

def death_file(who):
    if _files is None:
        _scan_files()
    return _deaths.get((who or "").lower())


def play_death(who, volume=1.0):
    path = death_file(who)
    if not path or not pygame.mixer.get_init():
        return 0
    try:
        snd = _clean.get("death:" + who) or _load_sound(path)
        _clean["death:" + who] = snd
        snd.set_volume(min(1.0, _effective_volume() * volume * VOICE_GAIN))
        ch = snd.play()
        if ch is not None:
            _extra[:] = [c for c in _extra if c.get_busy()] + [ch]
        return int(snd.get_length() * 1000)
    except Exception as exc:
        print(f"[voice] death scream for {who} failed: {exc}")
        return 0


def scream_onset(speaker, text):
    """Seconds into a line's clip where a baked-in scream starts, else None."""
    vo_id = find_line(speaker, text)
    if not vo_id or not has_file(vo_id):
        return None
    try:
        from audio.voice_manifest import DEATH_AT
        if vo_id in DEATH_AT:
            return DEATH_AT[vo_id]
    except Exception:
        pass
    if vo_id in _onsets:
        return _onsets[vo_id]
    res = None
    try:
        if pygame.mixer.get_init():
            snd = _clean.get(vo_id) or _load_sound(_files[vo_id])
            _clean[vo_id] = snd
            rate, size, chans = pygame.mixer.get_init()
            if abs(size) == 16:
                words = _speech_units(text) * _speaker_rate(speaker, vo_id)
                res = _find_scream(array.array("h", snd.get_raw()), rate, chans, words)
                print(f"[voice] {vo_id} ({speaker}): clip {snd.get_length():.2f}s, words ~{words:.2f}s, "
                      + (f"scream starts at {res:.2f}s -> shot lands there" if res is not None
                         else "no scream found -> shot on the last word")
                      + "  (override: voice_manifest.DEATH_AT)")
    except Exception as exc:
        print(f"[voice] scream scan failed for {vo_id}: {exc}")
    _onsets[vo_id] = res
    return res


def _speaker_rate(speaker, skip_id):
    """Seconds per speech unit for this actor, measured from their OTHER
    recorded lines (falls back to every recorded line, then a default)."""
    texts = {vo: (sp, t) for vo, sp, t in VOICE_LINES}
    mine, every = [], []
    for vo, path in (_files or {}).items():
        if vo == skip_id or vo not in texts:
            continue
        d = _duration(path)
        u = _speech_units(texts[vo][1])
        if not d or u < 8:
            continue
        r = d / u
        every.append(r)
        if texts[vo][0].upper() == (speaker or "").upper():
            mine.append(r)
    for pool in (mine, every):
        if len(pool) >= 1 and (pool is mine or len(pool) >= 3):
            pool.sort()
            return max(0.035, min(0.11, pool[len(pool) // 2]))
    return 0.062


def _find_scream(pcm, rate, chans, words_s=None, win_s=0.02):
    """Where a scream tacked onto the end of a line starts (seconds), or None.

    1. Expected end of the words = first sound + reading time at this
       actor's own speaking rate. If the clip runs well past that, the
       rest is the scream.
    2. Inside a window around that point, pick the sharpest jump in
       loudness (quiet just before, loud just after) - a scream onset,
       even when the line itself is shouted.
    3. Fallback with no estimate: a stretch clearly louder than the speech."""
    w = max(1, int(rate * win_s)) * chans
    env = []
    for i in range(0, len(pcm) - w + 1, w):
        blk = pcm[i:i + w:chans * 2] or pcm[i:i + w]
        env.append(math.sqrt(sum(x * x for x in blk) / len(blk)))
    n = len(env)
    if n < 25:
        return None
    pk = max(env)
    if pk < 400:
        return None
    s0 = next(i for i, e in enumerate(env) if e > 0.1 * pk)
    end = n - 1
    while end > s0 and env[end] < 0.06 * pk:
        end -= 1
    W = lambda sec: max(1, int(sec / win_s))

    def mean(a, b):
        a, b = max(0, a), min(n, b)
        return sum(env[a:b]) / max(1, b - a)

    if words_s:
        exp = s0 + W(words_s)
        if end - exp < W(0.35):
            return None                      # clip ends about when the words do
        lo, hi = max(s0 + W(0.3), exp - W(0.6)), min(end - W(0.25), exp + W(0.7))
        best, bi = None, None
        for i in range(lo, hi + 1):
            after, before = mean(i, i + W(0.25)), mean(i - W(0.08), i)
            score = after - 1.3 * before
            if best is None or score > best:
                best, bi = score, i
        if bi is not None and best > 0.08 * pk:
            while bi > lo and env[bi - 1] < env[bi] and env[bi - 1] > 0.15 * pk:
                bi -= 1                      # back up to the start of the rise
            return bi * win_s
        return exp * win_s                   # no clear edge: trust the estimate
    p = env.index(pk)
    if p < s0 + W(0.45) or p < n * 0.4:
        return None
    on = p
    while on > s0 and env[on - 1] > 0.3 * pk:
        on -= 1
    speech = sorted(e for e in env[s0:on] if e > 0.08 * pk)
    if len(speech) < 8:
        return None
    med = speech[len(speech) // 2]
    tail = sum(1 for e in env[on:] if e > 0.25 * pk)
    if med > 0.62 * pk or tail * win_s < 0.25:
        return None
    return on * win_s


def rescan():
    """Pick up newly dropped files without restarting (dev convenience)."""
    global _files
    _files = None
    _deaths.clear()
    _onsets.clear()
    _clean.clear()
    _radio.clear()
