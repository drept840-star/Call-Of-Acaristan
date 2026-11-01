"""Render the Call of Acaristan OST (tools/ost/album.py).

    python tools/build_ost.py              # all 8 tracks
    python tools/build_ost.py 1 7          # only tracks 1 and 7
    python tools/build_ost.py --wav-only   # skip the MP3 encode

WAV masters go to build/ost/, MP3s (192 kbps, tagged) to assets/music/ost/.
Run from the repo root. MP3 needs ffmpeg on PATH.
"""
import os
import re
import shutil
import subprocess
import sys
import time

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ost.album import ALBUM  # noqa: E402
from ost.synth import SR  # noqa: E402

WAV_DIR = os.path.join("build", "ost")
MP3_DIR = os.path.join("assets", "music", "ost")
ALBUM_NAME = "Call of Acaristan (Original Soundtrack)"


def slug(title):
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def main(argv):
    wav_only = "--wav-only" in argv
    picks = {int(a) for a in argv if a.isdigit()}
    ffmpeg = shutil.which("ffmpeg")
    if not wav_only and not ffmpeg:
        print("ffmpeg not found; writing WAV only")
        wav_only = True
    os.makedirs(WAV_DIR, exist_ok=True)
    os.makedirs(MP3_DIR, exist_ok=True)
    for no, (title, sub, build) in enumerate(ALBUM, 1):
        if picks and no not in picks:
            continue
        t0 = time.time()
        x = build().render()
        name = f"{no:02d}_{slug(title)}"
        wav = os.path.join(WAV_DIR, name + ".wav")
        wavfile.write(wav, SR, (np.clip(x, -1, 1).T * 32767).astype(np.int16))
        peak = 20 * np.log10(np.max(np.abs(x)) + 1e-9)
        print(f"{no:02d} {title:<20} {x.shape[1] / SR:6.1f}s  peak {peak:5.1f} dBFS  {time.time() - t0:5.1f}s render")
        if wav_only:
            continue
        mp3 = os.path.join(MP3_DIR, name + ".mp3")
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", wav, "-codec:a", "libmp3lame", "-b:a", "192k",
                        "-metadata", f"title={title}", "-metadata", f"comment={sub}",
                        "-metadata", f"album={ALBUM_NAME}", "-metadata", "artist=Call of Acaristan",
                        "-metadata", f"track={no}/{len(ALBUM)}", mp3], check=True)


if __name__ == "__main__":
    main(sys.argv[1:])
