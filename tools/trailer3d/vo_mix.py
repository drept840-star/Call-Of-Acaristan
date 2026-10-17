"""Place the trailer narration on the 80 s music cut and mix it.

    python tools/trailer3d/vo_mix.py
      in : assets/voice/Trailer/*.wav  (TR_01..TR_10 names win, else oldest-first
           by the time in the TTS file name, like the game's voice matcher)
           assets/music/trailer_music_80s.wav  (tools/trailer3d/music_cut.py)
      out: assets/music/trailer_mix_80s.wav      music + voice, ducked
           tools/trailer3d/timeline.json         where every line sits (for the shots)

Line lengths don't need to match anything: each clip is trimmed of edge
silence, long internal pauses are tightened (except the dramatic ones) and the
clip is placed by an anchor rule below. Overlaps raise an error.
"""
import json
import os
import re
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from music_cut import MARKS, SR, TOTAL  # noqa: E402

VO_DIR = os.path.join(ROOT, "assets", "voice", "Trailer")
MUSIC = os.path.join(ROOT, "assets", "music", "trailer_music_80s.wav")
OUT = os.path.join(ROOT, "assets", "music", "trailer_mix_80s.wav")
TIMELINE = os.path.join(HERE, "timeline.json")

TEXT = {
    "TR_01": "The Kilemeno Ocean. Still a graveyard.",
    "TR_02": "Route 12 was supposed to end it. / One ambush. One file. One operator who did what he was told.",
    "TR_03": "But files have copies. / And someone in the capital has been reading his.",
    "TR_04": "Martial law came on a Tuesday. / The tanks keep the highways open. / The curfew keeps the questions unasked.",
    "TR_05": "A clerk kept a notebook. / Names. Dates. Prices.",
    "TR_06": "Route 12 was never an ambush. / It was a sale.",
    "TR_07": "And the Presidential Guard has a new face. / Same intake. Same training. / Officially, he died two years ago.",
    "TR_08": "Everyone in Acaristan answers to someone.",
    "TR_09": "Some orders you follow. / Some you finish.",
    "TR_10": "Call of Acaristan.",
}
KEEP_PAUSES = {"TR_06", "TR_09"}      # silences that are part of the delivery
MAX_PAUSE = 0.4
GAP = 0.35                            # breath between consecutive lines
VO_RMS_DB = -17.0                     # narration loudness (RMS dBFS, after soft limiting)
MUSIC_UNDER_DB = -26.0                # music RMS under narration (ducked to this, 3-14 dB)
VO_GAIN = 0.62                        # pre-limiter peak normalisation


def _order_key(path):
    n = os.path.basename(path)
    m = re.search(r"(\d+)_(\d+)(?:_(\d+))?\s*([AP]M)(?:\((\d+)\))?", n, re.I)
    if not m:
        return (9e9, os.path.getmtime(path))
    h, mi = int(m.group(1)) % 12, int(m.group(2))
    sec = int(m.group(3) or 0)
    if m.group(4).upper() == "PM":
        h += 12
    return (h * 3600 + mi * 60 + sec + int(m.group(5) or 0) * 0.01, 0)


def find_files():
    files = sorted(f for f in os.listdir(VO_DIR) if f.lower().endswith((".wav", ".mp3", ".ogg", ".flac")))
    named = {os.path.splitext(f)[0].upper(): os.path.join(VO_DIR, f)
             for f in files if re.match(r"TR_\d\d$", os.path.splitext(f)[0], re.I)}
    rest = sorted((os.path.join(VO_DIR, f) for f in files
                   if os.path.splitext(f)[0].upper() not in named), key=_order_key)
    out = {}
    for vid in TEXT:
        if vid in named:
            out[vid] = named[vid]
        elif rest:
            out[vid] = rest.pop(0)
    return out


def _load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                          "-af", "highpass=f=70", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def _clean(x, tighten):
    hop = SR // 100
    e = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, len(x) - hop, hop)])
    db = 20 * np.log10(e + 1e-7)
    on = db > db.max() - 35
    idx = np.where(on)[0]
    a, b = max(0, idx[0] - 3), min(len(on), idx[-1] + 8)        # keep breath + tail
    on = on[a:b]
    x = x[a * hop:b * hop]
    if tighten:
        keep, run = [], 0
        lim = int(MAX_PAUSE * 100)
        for k, v in enumerate(on):
            run = 0 if v else run + 1
            keep.append(v or run <= lim // 2 or (k + (lim // 2)) >= len(on) or any(on[k:k + lim // 2 + 1]))
        mask = np.repeat(np.array(keep), hop)[:len(x)]
        x = x[:len(mask)][mask]
    pk = np.abs(x).max() + 1e-9
    fade = int(0.01 * SR)
    x = x * (VO_GAIN / pk)
    # level to VO_RMS_DB, soft-limit peaks (narration needs to sit on top of braams)
    act = x[np.abs(x) > 0.02]
    rms = np.sqrt(np.mean(act ** 2)) if len(act) else 0.1
    x = x * (10 ** (VO_RMS_DB / 20) / rms)
    x = np.tanh(x * 1.4) / 1.4
    x[:fade] *= np.linspace(0, 1, fade)
    x[-fade:] *= np.linspace(1, 0, fade)
    return x


def _phrase_starts(x):
    hop = SR // 100
    e = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, len(x) - hop, hop)])
    on = 20 * np.log10(e + 1e-7) > 20 * np.log10(e.max() + 1e-7) - 35
    starts, quiet = [0.0], 0
    for k, v in enumerate(on):
        if v and quiet >= 30:
            starts.append(k / 100)
        quiet = 0 if v else quiet + 1
    return starts


def place(clips):
    """Anchor rules -> {id: start seconds}. Raises on overlaps."""
    L = {k: len(v) / SR for k, v in clips.items()}
    t = {"TR_01": 1.0, "TR_02": MARKS["hit_biribel"] + 0.1}
    # "It was a sale." (last phrase of TR_06) lands just inside the music hole
    t["TR_06"] = MARKS["sold_start"] + 0.4 - _phrase_starts(clips["TR_06"])[-1]
    # TR_02..TR_05 run back to back; breaths shrink (down to 0.12 s) to fit
    chain = ("TR_02", "TR_03", "TR_04", "TR_05")
    room = t["TR_06"] - 0.15 - t["TR_02"] - sum(L[k] for k in chain)
    gap = max(0.12, min(GAP, room / len(chain)))
    for prev, cur in zip(chain, chain[1:]):
        t[cur] = t[prev] + L[prev] + gap
    t["TR_07"] = MARKS["hit_ucilev"] + 0.35
    t["TR_08"] = MARKS["hit_scopes"] - 0.25 - L["TR_08"]     # ends in the dip before the hit
    t["TR_09"] = MARKS["hit_scopes"] + 0.6
    t["TR_10"] = MARKS["hit_logo"] + 0.7
    ids = list(TEXT)
    for a, b in zip(ids, ids[1:]):
        if t[a] + L[a] > t[b] - 0.15:
            raise SystemExit("VO overlap: %s ends %.2f, %s starts %.2f" % (a, t[a] + L[a], b, t[b]))
    if t["TR_09"] + L["TR_09"] > MARKS["silence"][0] + 0.3:
        raise SystemExit("TR_09 runs into the gunshot")
    return t


def build():
    paths = find_files()
    missing = [k for k in TEXT if k not in paths]
    if missing:
        raise SystemExit("missing narration: %s" % missing)
    clips = {k: _clean(_load(p), k not in KEEP_PAUSES) for k, p in paths.items()}
    starts = place(clips)
    with wave.open(MUSIC) as w:
        m = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, 2) / 32768.0
    n = len(m)
    vo = np.zeros(n)
    for k, x in clips.items():
        a = int(starts[k] * SR)
        vo[a:a + len(x)] += x[:max(0, n - a)]
    # duck: per line, pull the music down to MUSIC_UNDER_DB (3..14 dB), smoothed
    hop = SR // 100
    target = np.zeros(n // hop + 1)
    mono = m.mean(axis=1)
    for k, x in clips.items():
        a = int(starts[k] * SR); b = min(n, a + len(x))
        mr = 20 * np.log10(np.sqrt(np.mean(mono[a:b] ** 2)) + 1e-9)
        d = max(-14.0, min(-3.0, MUSIC_UNDER_DB - mr))
        target[a // hop:b // hop + 1] = np.minimum(target[a // hop:b // hop + 1], d)
    sm = np.zeros_like(target); g = 0.0
    for i, v in enumerate(target):
        g = g + (v - g) * (0.25 if v < g else 0.03)          # fast duck, slow recover
        sm[i] = g
    gain = np.repeat(10 ** (sm / 20), hop)[:n]
    mix = m * gain[:, None] + vo[:, None] * np.array([[1.0, 1.0]])
    pk = np.abs(mix).max()
    if pk > 0.98:
        mix *= 0.98 / pk
    with wave.open(OUT, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    tl = {"total": TOTAL, "marks": MARKS,
          "vo": [{"id": k, "start": round(starts[k], 3), "end": round(starts[k] + len(clips[k]) / SR, 3),
                  "text": TEXT[k], "file": os.path.relpath(paths[k], ROOT).replace("\\", "/")}
                 for k in TEXT]}
    with open(TIMELINE, "w", encoding="utf-8") as fh:
        json.dump(tl, fh, indent=1)
    return tl


if __name__ == "__main__":
    tl = build()
    for v in tl["vo"]:
        print("%s %6.2f-%6.2f  %s" % (v["id"], v["start"], v["end"], v["text"][:60]))
    print("->", OUT)
