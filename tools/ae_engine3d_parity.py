#!/usr/bin/env python3
"""AE ENGINE3D PARITY - software-backend determinism evidence.

RPE6 Phase 10 (M4, scope call 4). The GL-vs-software diff itself is
an owner-machine run (`tools/engine3d_check.py` - the sandbox has no
GL); what CI can prove everywhere is that the software backend -
the one every sandbox golden is rendered with - is deterministic:

  1. the M2 ambush film (missions.m2.sniper3d.SniperCinematic)
     rendered twice from fresh instances is pixel-identical;
  2. re-rendering a frame after other frames have been drawn is
     pixel-identical (no cross-frame state leakage);
  3. the Mission 0 depot set rendered through render3d_bridge +
     engine3d twice is pixel-identical.

Prints "AE ENGINE3D PARITY: OK ..." and exits 0 on success.
"""
import os
import sys


def _arr(surf):
    import numpy as np
    import pygame
    return pygame.surfarray.array3d(surf).copy()


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ["ACARISTAN_RENDERER"] = "software"
    sys.path.insert(0, os.path.join(root, "src"))
    os.chdir(root)
    import numpy as np
    import pygame
    pygame.init()
    screen = pygame.display.set_mode((1000, 700))

    from missions.m2.sniper3d import SniperCinematic
    a = SniperCinematic()
    b = SniperCinematic()
    times = [a.shots[-1][1] * k / 8 for k in (2, 5)]
    frames = {}
    for t in times:
        a.t = t
        a.draw(screen)
        fa = _arr(a.r.surface)
        b.t = t
        b.draw(screen)
        fb = _arr(b.r.surface)
        assert np.array_equal(fa, fb), f"sniper film t={t}: instances differ"
        frames[t] = fa
    # interleave: draw later frame, then re-draw the earlier one
    a.t = times[1]
    a.draw(screen)
    a.t = times[0]
    a.draw(screen)
    assert np.array_equal(_arr(a.r.surface), frames[times[0]]), \
        "sniper film: re-render after interleave differs"

    # Mission 0 depot set through the data bridge, twice
    from game import render3d_bridge
    prims = render3d_bridge.set_prims("mission0.depot")
    assert prims
    from missions import m0
    surf = pygame.Surface((480, 270))
    m0._draw_depot3d(surf, 800)
    first = _arr(surf)
    m0._draw_depot3d(surf, 800)
    assert np.array_equal(_arr(surf), first), "m0 depot set: re-render differs"

    print("AE ENGINE3D PARITY: OK (software backend deterministic: "
          "M2 film x2 frames x2 instances + interleave, m0 depot set x2; "
          "GL diff = owner-machine run of tools/engine3d_check.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
