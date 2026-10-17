#!/usr/bin/env python3
"""Re-master audio only: reuse the kept premix.wav, re-run normalise + mux.

Usage: python tools/mp_remaster.py <assembler_workdir>
    <assembler_workdir> = a mp_trailer_assemble.py --keep-stems run dir
    containing premix.wav + silent_master.mp4.
"""
import shutil, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mp_trailer_assemble as A

if len(sys.argv) != 2:
    sys.exit("usage: python tools/mp_remaster.py <assembler_workdir>  "
             "(a mp_trailer_assemble.py --keep-stems run with premix.wav "
             "+ silent_master.mp4)")
SRC = Path(sys.argv[1])
SRC_PREMIX = SRC / "premix.wav"
work = Path(tempfile.mkdtemp(prefix="mp_remaster_"))
premix = work / "premix.wav"
shutil.copy2(SRC_PREMIX, premix)

audio = A.normalise(work, premix)

A.run([A.FFMPEG, "-y", "-i", SRC / "silent_master.mp4",
       "-i", audio, "-map", "0:v", "-map", "1:a",
       "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
       "-movflags", "+faststart", str(A.OUT_FINAL)],
      f"mux -> {A.OUT_FINAL.name}")
shutil.copy2(A.OUT_FINAL, A.OUT_PROJECT)
d = A.dur_of(A.OUT_FINAL)
print(f"REMASTERED {A.OUT_FINAL} {d:.2f}s {A.OUT_FINAL.stat().st_size/1e6:.1f} MB")
sys.stdout.flush()
import os
os._exit(0)

