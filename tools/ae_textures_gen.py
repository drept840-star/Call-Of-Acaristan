#!/usr/bin/env python3
"""AE TEXTURES GEN - deterministic palette textures (RPE6 Phase 11 step 9).

Writes src/game/content/textures/<id>.texture.json (schema ae.texture/1):
16x16 palette-indexed pixel rows, seeded - regenerate, never hand-edit
the outputs. Software renderer samples them nearest (retro look).

    python3 tools/ae_textures_gen.py
"""
import json
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "src", "game", "content", "textures")


def _speckle(rng, rows, chars_weights, w=16, h=16):
    chars, weights = zip(*chars_weights)
    for y in range(h):
        rows.append("".join(rng.choices(chars, weights)[0] for _ in range(w)))
    return rows


def concrete():
    rng = random.Random(7101)
    rows = _speckle(rng, [], [(".", 78), (":", 12), ("o", 8), ("+", 2)])
    # two hairline cracks (random walks)
    for x0 in (3, 11):
        x = x0
        for y in range(16):
            rows[y] = rows[y][:x] + "+" + rows[y][x + 1:]
            x = max(0, min(15, x + rng.choice((-1, 0, 0, 1))))
    return {
        "schema": "ae.texture/1", "id": "concrete", "size": [16, 16],
        "palette": {".": [104, 102, 98], ":": [122, 120, 112],
                    "o": [86, 84, 80], "+": [66, 64, 60]},
        "rows": rows,
    }


def wood_crate():
    rng = random.Random(7202)
    rows = []
    for y in range(16):
        if y % 4 == 3:
            rows.append("=" * 16)
            continue
        row = []
        for x in range(16):
            r = rng.random()
            row.append("W" if r < 0.16 else "d" if r < 0.30 else "w")
        rows.append("".join(row))
    for y in (0, 4, 8, 12):  # nails near the plank ends
        for x in (1, 14):
            rows[y] = rows[y][:x] + "n" + rows[y][x + 1:]
    return {
        "schema": "ae.texture/1", "id": "wood_crate", "size": [16, 16],
        "palette": {"w": [146, 110, 66], "W": [164, 128, 80],
                    "d": [118, 86, 48], "=": [94, 66, 38],
                    "n": [58, 48, 42]},
        "rows": rows,
    }


def asphalt():
    rng = random.Random(7303)
    rows = _speckle(rng, [], [("a", 72), ("s", 16), ("k", 9), ("l", 3)])
    return {
        "schema": "ae.texture/1", "id": "asphalt", "size": [16, 16],
        "palette": {"a": [54, 56, 60], "s": [68, 70, 74],
                    "k": [40, 42, 46], "l": [88, 90, 94]},
        "rows": rows,
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn in (concrete, wood_crate, asphalt):
        tex = fn()
        path = os.path.join(OUT, tex["id"] + ".texture.json")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(tex, fh, indent=1)
            fh.write("\n")
        print("wrote", os.path.relpath(path, ROOT))
    print("AE TEXTURES GEN: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
