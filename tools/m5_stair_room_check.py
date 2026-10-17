"""Regression: interiors cover the frame and both stair actors remain visible.

Run once with ACARISTAN_RENDERER=software and once with =gl. Screenshots
are diagnostic output only; this tool never starts missions or writes saves.
"""
import os
from pathlib import Path
import sys
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    import numpy as np
    import pygame
    from core import config
    from cutscenes import m5mid3d as mid, m5martial3d as film

    out = ROOT / "outputs" / "stair_room_check" / os.environ.get("ACARISTAN_RENDERER", "auto")
    out.mkdir(parents=True, exist_ok=True)
    screen = pygame.Surface(config.screen.get_size())
    r, _ = film._rend()
    print("backend:", type(r).__name__)
    real_person = mid._person

    def sentinel(w, h, top, bot):
        s = pygame.Surface((w, h))
        s.fill((255, 0, 255))
        return s

    def render(fn, ms, hide=None):
        def person(renderer, key, *args):
            if key != hide:
                return real_person(renderer, key, *args)
        with patch.object(film, "_sky", side_effect=sentinel), patch.object(film, "_finish"), patch.object(mid, "_person", side_effect=person):
            fn(screen, ms)
        return pygame.surfarray.array3d(screen).copy()

    for ms in (0, 300, 1000, 2000, 2800, 3700, 4200):
        frame = render(mid._basement_descent, ms)
        band = frame[:, mid.SAFE_TOP:mid.SAFE_BOT]
        uncovered = (band[:, :, 0] > 245) & (band[:, :, 1] < 8) & (band[:, :, 2] > 245)
        ratio = float(uncovered.mean())
        assert ratio < 0.003, (ms, "exposed background", ratio)
        for key in ("biribel", "maru"):
            without = render(mid._basement_descent, ms, key)
            visible = int((np.abs(frame.astype(int) - without.astype(int)).sum(axis=2) > 15).sum())
            assert visible > 100, (ms, key, "actor hidden", visible)
        mid._basement_descent(screen, ms)
        pygame.image.save(screen, str(out / ("descent_%04d.png" % ms)))
        print("descent", ms, "enclosed; both actors visible; uncovered=", round(ratio, 6))

    # These room sets had the same absent fourth wall / ceiling pattern.
    for name in ("m5x_vasile_wide", "m5x_vasile_close", "m5x_vasile_biribel", "m5x_vasile_lean", "m5x_maru_two", "m5x_maru_close", "m5x_maru_biribel"):
        frame = render(mid.M5X_SCENES[name], 1500)
        band = frame[:, mid.SAFE_TOP:mid.SAFE_BOT]
        uncovered = (band[:, :, 0] > 245) & (band[:, :, 1] < 8) & (band[:, :, 2] > 245)
        assert float(uncovered.mean()) < 0.003, (name, "room shell incomplete", float(uncovered.mean()))
        print(name, "room coverage: OK")
    for z in (0, 0.25, 1.25, 3.25, 5.75, 6.0, 6.7):
        expected = max(0.0, 2.4 - int(z / 0.5) * 0.2)
        assert abs(mid._stair_height(z) - expected) < 1e-8
    mid._basement_descent_2d(screen, 2200)
    pygame.image.save(screen, str(out / "fallback.png"))
    print("STAIR ROOM CHECK: OK")


if __name__ == "__main__":
    main()
