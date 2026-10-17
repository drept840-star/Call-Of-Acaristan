#!/usr/bin/env python3
"""AE PROOF SHEET - side-by-side before/after sheet for Phase 11 steps.

    python3 tools/ae_proof_sheet.py --before previews/upgrades3d/before \
        --after previews/upgrades3d/step4 --out previews/upgrades3d/step4/sheet.png \
        [--depot-before previews/upgrades3d/step1] [--title "Step 4 - baked AO"]
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELL_W = 480


def _load_scaled(path):
    import pygame
    s = pygame.image.load(path)
    w, h = s.get_size()
    return pygame.transform.smoothscale(s, (CELL_W, int(h * CELL_W / w)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--depot-before", default=None)
    ap.add_argument("--title", default="Phase 11 proof sheet")
    args = ap.parse_args()
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((64, 64))
    font = pygame.font.Font(None, 30)
    small = pygame.font.Font(None, 24)

    rows = []
    scenes = [("office", "Vasile's office (M5, set data + actors)"),
              ("depot", "Mission 0 depot (set data)"),
              ("film", "M2 ambush film (actors)")]
    if os.path.exists(os.path.join(args.after, "yard.png")) and \
            os.path.exists(os.path.join(args.after, "yard_off.png")):
        scenes.append(("yard", "Mission 0 yard (weather on/off)"))
    for name, label in scenes:
        bdir = args.before
        if name == "depot" and args.depot_before:
            bdir = args.depot_before
        if name == "yard":
            b = _load_scaled(os.path.join(args.after, "yard_off.png"))
            a = _load_scaled(os.path.join(args.after, "yard.png"))
            rows.append((label, b, a))
            continue
        b = _load_scaled(os.path.join(bdir, f"{name}.png"))
        a = _load_scaled(os.path.join(args.after, f"{name}.png"))
        rows.append((label, b, a))

    row_h = max(b.get_height() for _, b, _ in rows) + 58
    sheet = pygame.Surface((CELL_W * 2 + 24, row_h * len(rows) + 64))
    sheet.fill((24, 24, 28))
    sheet.blit(font.render(args.title, True, (240, 230, 200)), (12, 10))
    sheet.blit(small.render("BEFORE", True, (200, 200, 210)), (12, 40))
    sheet.blit(small.render("AFTER", True, (200, 240, 200)), (CELL_W + 12, 40))
    y = 64
    for label, b, a in rows:
        sheet.blit(small.render(label, True, (180, 180, 190)), (12, y + 2))
        sheet.blit(b, (0, y + 26))
        sheet.blit(a, (CELL_W + 24, y + 26))
        y += row_h
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    pygame.image.save(sheet, args.out)
    print(f"AE PROOF SHEET: OK -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
