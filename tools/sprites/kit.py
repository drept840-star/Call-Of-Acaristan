"""kit.py - shared machinery for the tools/sprites/<family>.py generators.

Every family generator builds a list of named frames and hands it to
``run(family, build)``. This module owns everything the generators must do
identically (Polish Task 7 contract):

  * deterministic output - generators seed ``random.Random`` from constants
    only; sheets are packed in insertion order; JSON is written with sorted
    keys and LF line endings, so two runs are byte-identical;
  * sprite sheet + JSON metadata (frame rects, anchors/pivots, timings,
    variants) written to ``assets/art/<sheet>.png/.json`` - the same folder
    ``core.artpack`` already loads from (no parallel pipeline);
  * pixel-art helpers in the house style (upper-left key light, 1 px
    darker-hue outline, flat tone ramps, AO, flat alpha shadows);
  * ``--preview``: contact sheet on light and dark backgrounds at 2x
    nearest-neighbour into ``previews/sprites/<family>.png``;
  * ``--out DIR``: write somewhere else (the smoke test hashes two runs in a
    temp dir to prove determinism).

pygame only, no game imports.
"""
import argparse
import importlib.util
import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import palette as P  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ART_DIR = os.path.join(ROOT, "assets", "art")
PREVIEW_DIR = os.path.join(ROOT, "previews", "sprites")


def _load_m5_kit():
    # The M5 kit is the house-style reference and owns the 5x7 stencil font.
    # Loaded by path so no game package (__init__ side effects) is imported.
    p = os.path.join(ROOT, "src", "game", "art", "m5", "_kit.py")   # RPE6 Phase 3: pack moved (A-008)
    spec = importlib.util.spec_from_file_location("_aca_m5_kit", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M5 = _load_m5_kit()
text = M5.text
text_w = M5.text_w


def init():
    if not pygame.get_init():
        pygame.init()


def new(w, h):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    return s


def rrect(surf, col, rect, r=0, width=0):
    pygame.draw.rect(surf, col, rect, width, border_radius=r)


def outline(surf, col=None, sides=4):
    """1 px outline OUTSIDE the opaque silhouette; returns a new surface.

    ``col`` None -> darker hue of the neighbouring fill pixel (house rule:
    outlines are a darker, slightly cooler hue - never flat black). Done
    with four shifted, darkened copies under the original, so it is pure
    C blits and cheap enough for 400 px wrecks.
    """
    w, h = surf.get_size()
    dark = surf.copy()
    if col is None:
        dark.fill((92, 96, 112, 255), special_flags=pygame.BLEND_RGBA_MULT)
    else:
        dark.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        dark.fill((*col, 0), special_flags=pygame.BLEND_RGBA_ADD)
    out = new(w, h)
    offs = ((1, 0), (-1, 0), (0, 1), (0, -1))
    if sides == 8:
        offs += ((1, 1), (-1, -1), (1, -1), (-1, 1))
    for dx, dy in offs:
        out.blit(dark, (dx, dy))
    out.blit(surf, (0, 0))
    return out


def inner_line(surf, rect, col_tl, col_br):
    """Selective interior edge: lit top/left, shaded bottom/right."""
    x, y, w, h = rect
    surf.fill(col_tl, (x, y, w, 1))
    surf.fill(col_tl, (x, y, 1, h))
    surf.fill(col_br, (x, y + h - 1, w, 1))
    surf.fill(col_br, (x + w - 1, y, 1, h))


def shadow(surf, rect, r=6, alpha=(70, 40), grow=3):
    """Flat two-step drop shadow (no blur): falls down-right of ``rect``."""
    x, y, w, h = rect
    lay = new(*surf.get_size())
    rrect(lay, (0, 0, 0, alpha[1]), (x - grow + 2, y - grow + 3, w + grow * 2, h + grow * 2), r + grow)
    rrect(lay, (0, 0, 0, alpha[0]), (x + 2, y + 3, w, h), r)
    surf.blit(lay, (0, 0))


def ellipse_shadow(surf, rect, alpha=(70, 38)):
    x, y, w, h = rect
    lay = new(*surf.get_size())
    pygame.draw.ellipse(lay, (0, 0, 0, alpha[1]), (x - 2, y - 1, w + 4, h + 2))
    pygame.draw.ellipse(lay, (0, 0, 0, alpha[0]), (x + 2, y + 1, w - 4, h - 2))
    surf.blit(lay, (0, 0))


def ao_band(surf, rect, alpha=60, height=3, edge="bottom"):
    """Ambient occlusion: stepped (not blurred) dark band at a contact edge."""
    x, y, w, h = rect
    lay = new(*surf.get_size())
    for i in range(height):
        a = int(alpha * (height - i) / height)
        if edge == "bottom":
            lay.fill((0, 0, 0, a), (x, y + h - 1 - i, w, 1))
        else:
            lay.fill((0, 0, 0, a), (x, y + i, w, 1))
    surf.blit(lay, (0, 0), special_flags=0)


def dither(surf, rect, col, step=2, phase=0):
    """Checker dither - only for broad tonal transitions where it reads."""
    x, y, w, h = rect
    for yy in range(y, y + h):
        for xx in range(x + ((yy + phase) % step), x + w, step):
            if surf.get_at((xx, yy))[3]:
                surf.set_at((xx, yy), col)


def mask_to(surf, clip):
    """Zero alpha of ``surf`` wherever ``clip`` is transparent."""
    w, h = surf.get_size()
    for y in range(h):
        for x in range(w):
            if clip.get_at((x, y))[3] == 0:
                surf.set_at((x, y), (0, 0, 0, 0))


class Sheet:
    """Ordered frame list -> shelf-packed atlas + JSON metadata."""

    def __init__(self, name, family, pad=2, max_w=1024):
        self.name, self.family, self.pad, self.max_w = name, family, pad, max_w
        self.frames = []
        self.meta = {}

    def add(self, key, surf, anchor=(0, 0), **extra):
        assert all(k != key for k, *_ in self.frames), key
        self.frames.append((key, surf, tuple(int(a) for a in anchor), extra))

    def pack(self):
        x = y = row_h = 0
        W = 0
        rects = []
        for _k, s, _a, _e in self.frames:
            w, h = s.get_size()
            if x and x + w > self.max_w:
                x, y, row_h = 0, y + row_h + self.pad, 0
            rects.append((x, y, w, h))
            x += w + self.pad
            row_h = max(row_h, h)
            W = max(W, x - self.pad)
        H = y + row_h
        atlas = new(max(1, W), max(1, H))
        data = {}
        for (k, s, a, e), r in zip(self.frames, rects):
            atlas.blit(s, r[:2])
            d = {"rect": list(r), "anchor": list(a)}
            d.update(e)
            data[k] = d
        js = {"sheet": self.name, "family": self.family, "image": self.name + ".png",
              "size": [atlas.get_width(), atlas.get_height()], "scale": 1,
              "tile_size": P.T, "frames": data, "meta": self.meta}
        return atlas, js

    def save(self, out_dir):
        atlas, js = self.pack()
        os.makedirs(out_dir, exist_ok=True)
        pygame.image.save(atlas, os.path.join(out_dir, self.name + ".png"))
        with open(os.path.join(out_dir, self.name + ".json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(js, fh, indent=1, sort_keys=True)
            fh.write("\n")
        return atlas, js


def preview(family, sheets, path=None):
    """Contact sheet: every frame on a light row and a dark row, 2x nearest."""
    init()
    font = pygame.font.Font(None, 14)
    cells = [(k, s) for sh in sheets for (k, s, _a, _e) in sh.frames]
    cols, cw, chh = 6, 0, 0
    for _k, s in cells:
        cw, chh = max(cw, s.get_width() * 2 + 8), max(chh, s.get_height() * 2 + 18)
    rows = (len(cells) + cols - 1) // cols
    out = pygame.Surface((cols * cw * 2, rows * chh))
    for half, bg in enumerate(((196, 196, 190), (24, 24, 28))):
        out.fill(bg, (half * cols * cw, 0, cols * cw, rows * chh))
        fg = (20, 20, 20) if half == 0 else (220, 220, 210)
        for i, (k, s) in enumerate(cells):
            cx = half * cols * cw + (i % cols) * cw + 4
            cy = (i // cols) * chh + 2
            big = pygame.transform.scale(s, (s.get_width() * 2, s.get_height() * 2))
            out.blit(big, (cx, cy + 14))
            out.blit(font.render(k[:40], False, fg), (cx, cy))
    path = path or os.path.join(PREVIEW_DIR, family + ".png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pygame.image.save(out, path)
    return path


def run(family, build, argv=None):
    """CLI shared by all generators: [--out DIR] [--preview]."""
    ap = argparse.ArgumentParser(description="Generate the %s sprite sheets." % family)
    ap.add_argument("--out", default=ART_DIR, help="output folder (default assets/art)")
    ap.add_argument("--preview", action="store_true", help="write previews/sprites/%s.png" % family)
    a = ap.parse_args(argv)
    init()
    sheets = build()
    for sh in sheets:
        atlas, js = sh.save(a.out)
        print("%s: %s.png %dx%d, %d frames" % (family, sh.name, js["size"][0], js["size"][1], len(js["frames"])))
    if a.preview:
        print("preview ->", os.path.relpath(preview(family, sheets), ROOT))
    return 0
