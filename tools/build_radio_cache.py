"""Pre-build the radio-FX voice cache (assets/voice/_radio_cache).

The first play of a radio line runs a pure-Python filter chain (130-500 ms)
and writes the result there; every later play just loads the wav.  Without a
warm cache that is a half-second freeze the first time each line is heard in a
fight.  Run this once per machine:

    python tools/build_radio_cache.py [--speaker NAME] [--limit N]

Safe to re-run: lines that already have a cache file are only counted.
"""
import os
import sys
import time

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((64, 64))
from core.config import audio  # noqa: E402,F401  (initialises the mixer exactly like the game)
from audio import voice  # noqa: E402

speaker = None
limit = None
args = sys.argv[1:]
while args:
    a = args.pop(0)
    if a == "--speaker" and args:
        speaker = args.pop(0).lower()
    elif a == "--limit" and args:
        limit = int(args.pop(0))

if voice._files is None:
    voice._scan_files()
ids = sorted(voice._files)
if speaker:
    ids = [i for i in ids if speaker in os.path.dirname(voice._files[i]).lower()]
if limit:
    ids = ids[:limit]

built = kept = 0
t0 = time.perf_counter()
for n, vo in enumerate(ids, 1):
    t1 = time.perf_counter()
    voice._load(vo, True)
    ms = (time.perf_counter() - t1) * 1000.0
    # the Sound objects are big: the game keeps them, this tool must not
    voice._radio.pop(vo, None)
    voice._clean.pop(vo, None)
    if ms > 60.0:
        built += 1
    else:
        kept += 1
    if n % 25 == 0 or n == len(ids):
        print("%d/%d  built %d  already cached %d  (%.0f s)"
              % (n, len(ids), built, kept, time.perf_counter() - t0))
print("RADIO CACHE: OK" if ids else "RADIO CACHE: no voice files found")
