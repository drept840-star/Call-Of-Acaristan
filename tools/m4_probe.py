"""Probe the audio sound registry for names the M4 intro might reuse."""
import re
import sys

ROOT = "src/audio/audio.py"
s = open(ROOT, encoding="utf-8").read()

# Lazy generators: _gen_<name> -> registered as <name>
gens = sorted(set(re.findall(r"def (_gen_[a-z0-9_]+)\(", s)))
print("LAZY GEN NAMES:")
for g in gens:
    print("  ", g[5:])

# Static sound table entries: "name": (... or "name": load_sound(...)
print("\nSTATIC SOUNDS (sample):")
for m in re.finditer(r'"([a-z0-9_]+)":\s*(load_sound|load_music|\()', s):
    print("  ", m.group(1))

# Any cue name referenced anywhere in the cutscene shot lists
print("\nCUE NAMES IN M4 SHOTS:")
for shot in re.finditer(r'"cues":\s*\[(.*?)\]', s, re.S):
    pass
for line in s.splitlines():
    if "cues" in line or "m4_" in line:
        print("  ", line.strip()[:120])