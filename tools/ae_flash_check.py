#!/usr/bin/env python3
"""ae_flash_check - Phase 9 exit evidence: flash reduction caps the breach white-out.

Renders the M5 breach take (`m5x_breach`, the mid-cutscene flash beat) at
the flash-peak timestamps with flash reduction OFF and ON and measures
the maximum frame luminance.  Exit 0 when, with the setting enabled,
every sampled frame stays under the cap threshold and the peak is
materially below the un-capped peak.

    python tools/ae_flash_check.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THRESHOLD = 210.0          # /255 max luminance allowed with flash reduction on
SAMPLE_T = (560, 700, 900, 1100)   # ms; the breach flash starts at t=520


def _max_luminance(surf) -> float:
    import numpy as np
    import pygame
    arr = pygame.surfarray.array3d(surf).astype(np.float32)
    lum = arr[:, :, 0] * 0.2126 + arr[:, :, 1] * 0.7152 + arr[:, :, 2] * 0.0722
    return float(lum.max())


def main() -> int:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import ae_replay  # noqa: F401  (full boot)

    import pygame
    from core.user_settings import SETTINGS
    from cutscenes.m5mid3d import draw_m5x

    surf = pygame.Surface((1000, 700))
    results = {}
    for enabled in (False, True):
        SETTINGS.flash_reduction = enabled
        vals = []
        for t in SAMPLE_T:
            surf.fill((0, 0, 0))
            draw_m5x("m5x_breach", surf, t)
            vals.append(round(_max_luminance(surf), 1))
        results[enabled] = vals
    SETTINGS.flash_reduction = False

    off, on = results[False], results[True]
    print(f"AE FLASH: breach max luminance off={off} on={on} (cap {THRESHOLD})")
    ok = all(v <= THRESHOLD for v in on) and max(on) < max(off)
    print("AE FLASH: " + ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
