"""Convert assets/voice/**/*.wav to OGG Vorbis in place (RPE6 housekeeping, 2026-10-14).

Why: the mixer runs at 22.05 kHz (audio.SAMPLE_RATE), so the 24 kHz mono WAV
exports carry nothing the player can hear, and the voice loader already accepts
.ogg (voice._EXTS). ~77 kbps Vorbis is transparent for these clips and 5x smaller.

Safety: every OGG is written next to its WAV, re-read with libsndfile (frame
count must equal the source) and loaded with pygame.mixer before the WAV is
removed. Dry run by default; --apply converts. Needs: pip install soundfile.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICE = ROOT / "assets" / "voice"
LEVEL = 0.4   # libsndfile compression_level: 0 = best quality ... 1 = smallest; 0.4 ~ 77 kbps here


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    import soundfile as sf
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.mixer.init(frequency=22050, size=-16, channels=2)
    wavs = sorted(VOICE.rglob("*.wav"))
    before = after = 0
    bad = 0
    for w in wavs:
        o = w.with_suffix(".ogg")
        data, sr = sf.read(str(w), dtype="int16")
        before += w.stat().st_size
        if not a.apply:
            continue
        sf.write(str(o), data, sr, format="OGG", subtype="VORBIS", compression_level=LEVEL)
        d2, sr2 = sf.read(str(o), dtype="int16")
        ok = (len(d2) == len(data) and sr2 == sr)
        if ok:
            try:
                pygame.mixer.Sound(str(o))
            except Exception as exc:  # noqa: BLE001
                print("pygame cannot load", o, exc); ok = False
        if not ok:
            bad += 1
            o.unlink(missing_ok=True)
            print("KEPT WAV (verification failed):", w)
            continue
        after += o.stat().st_size
        w.unlink()
    n = len(wavs)
    print(f"VOICE->OGG: {'applied' if a.apply else 'dry run'} {n} files, {before/1e6:.1f} MB"
          + (f" -> {after/1e6:.1f} MB, {bad} kept as WAV" if a.apply else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
