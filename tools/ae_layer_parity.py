#!/usr/bin/env python3
"""Parity oracle for baked *chunk* layers (``game.art.<pack>.<name>`` adapters with ``bake_setup``):
re-runs the mission's runtime chunk cache (``core.staticlayer``) in the state ``bake_setup(variant)``
sets up and compares the full-world composite against the baked PNG, pixel for pixel.

    python tools/ae_layer_parity.py m3/archives_static [m4/world_static ...] [--all]

Exit 0 only if every compared variant is identical (max channel delta 0).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
if os.environ.get("PYTHONHASHSEED") != "0" and not os.environ.get("AE_NO_HASHSEED_PIN"):
    import subprocess as _sp
    sys.exit(_sp.call([sys.executable, *sys.argv], env=dict(os.environ, PYTHONHASHSEED="0")))

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="asset ids (pack/name)")
    ap.add_argument("--all", action="store_true", help="every layer with a bake_setup hook in packs m1..m4")
    args = ap.parse_args(argv)
    import importlib
    import numpy as np
    import pygame
    from engine.core import pin_wall
    from game.art._pack import Pack
    from core import staticlayer
    pin_wall(ms=lambda: 100_000, s=lambda: 100.0)
    ids = list(args.ids)
    if args.all:
        for pk in ("m1", "m2", "m3", "m4"):
            p = Pack(pk)
            if not os.path.exists(p.manifest_path()):
                continue
            for aid in p.ids():
                mod = importlib.import_module(p.registry().define(aid).module)
                if hasattr(mod, "bake_setup"):
                    ids.append(aid)
    bad = 0
    for aid in ids:
        pk, name = aid.split("/", 1)
        pack = Pack(pk)
        mod = pack.module(name)
        for v in range(getattr(mod, "VARIANTS", 1)):
            mod.bake_setup(v)
            baked_p = pack.baked_path(name, v)
            if not os.path.exists(baked_p):
                print(f"{aid} v{v}: MISSING baked file {baked_p}")
                bad += 1
                continue
            baked = pygame.image.load(baked_p)
            # live chunk composite via the painter's own render (same callback, baking flag raised)
            live = mod.render(v, 1)
            if live.get_size() != baked.get_size():
                print(f"{aid} v{v}: SIZE {live.get_size()} vs baked {baked.get_size()}")
                bad += 1
                continue
            a = pygame.surfarray.array3d(live).astype(np.int16)
            b = pygame.surfarray.array3d(baked).astype(np.int16)
            d = np.abs(a - b).max(axis=2)
            n = int(np.count_nonzero(d))
            # and the real runtime path: StaticLayer chunks blitted for a few cameras
            w, h = live.get_size()
            lay = staticlayer.StaticLayer(w, h)
            cb = getattr(mod, "runtime_callback", None)
            worst = 0
            if cb is not None:
                for cam in ((0, 0), (w // 3, h // 3), (w - 1000, h - 700)):
                    t = pygame.Surface((1000, 700)); t.fill((1, 2, 3))
                    lay.blit(t, cam[0], cam[1], cb())
                    u = pygame.Surface((1000, 700)); u.fill((1, 2, 3)); u.blit(baked, (-cam[0], -cam[1]))
                    dd = np.abs(pygame.surfarray.array3d(t).astype(np.int16) - pygame.surfarray.array3d(u).astype(np.int16)).max()
                    worst = max(worst, int(dd))
            verdict = "EXACT" if n == 0 and worst == 0 else "DIFFERENT"
            if verdict != "EXACT":
                bad += 1
            print(f"{aid} v{v}: render-vs-baked {n} px differ (max {int(d.max())}); runtime chunks vs baked max delta {worst} -> {verdict}")
    print("AE LAYER PARITY:", "OK" if bad == 0 else f"FAIL ({bad})")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
