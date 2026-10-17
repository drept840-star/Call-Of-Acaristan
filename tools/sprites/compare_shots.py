"""compare_shots.py - stitch T7 before/after shots side by side.

    python tools/sprites/compare_shots.py [--crop x,y,w,h] [--b64]

Writes shots/polish_pass/07/<family>/compare.png (before | after, magenta
gutter). --crop limits both shots to a region; --b64 prints the PNGs as
base64 lines (handy for remote review).
"""
import base64
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "shots" / "polish_pass" / "07"


def main():
    crop = None
    if "--crop" in sys.argv:
        crop = [int(v) for v in sys.argv[sys.argv.index("--crop") + 1].split(",")]
    for fam in sorted(p.name for p in SHOTS.iterdir() if p.is_dir()):
        b, a = SHOTS / fam / "before.png", SHOTS / fam / "after.png"
        if not (b.exists() and a.exists()):
            continue
        bi, ai = pygame.image.load(str(b)), pygame.image.load(str(a))
        if crop:
            bi, ai = bi.subsurface(crop), ai.subsurface(crop)
        w, h = bi.get_size()
        out = pygame.Surface((w * 2 + 6, h))
        out.fill((255, 0, 255))
        out.blit(bi, (0, 0))
        out.blit(ai, (w + 6, 0))
        dst = SHOTS / fam / "compare.png"
        pygame.image.save(out, str(dst))
        if "--b64" in sys.argv:
            print("%s:%s" % (fam, base64.b64encode(dst.read_bytes()).decode()))
        else:
            print("compare ->", dst.relative_to(ROOT))


if __name__ == "__main__":
    main()
