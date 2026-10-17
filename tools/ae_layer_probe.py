"""ae_layer_probe - can this camera-space painter become a baked world layer?

    python tools/ae_layer_probe.py missions.m3.draw _draw_cell_details [--kwargs '{"live": false}']
                                   [--map 48x48] [--tile 64] [--window 1000x700] [--pad 4] [--out build/probe.png]

1. Prints the painter's dynamic inputs (time, STATE, flow globals, unseeded
   random) so the static/live split can be decided.
2. Finds the world bounding rect of everything it draws (``layer_bounds``).
3. Bakes it (``bake_camera_layer``) and compares the live painter against the
   baked layer at a grid of camera positions on three backgrounds
   (``probe_layer``): 0 differing pixels = exact conversion.
Prints the ORIGIN/SIZE to paste into the ``game.art.<pack>`` adapter module.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
if os.environ.get("PYTHONHASHSEED") != "0" and not os.environ.get("AE_NO_HASHSEED_PIN"):
    import subprocess as _sp
    sys.exit(_sp.call([sys.executable, *sys.argv], env=dict(os.environ, PYTHONHASHSEED="0")))
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DYN = [(r"_now_ms\(|_now_s\(|now_ms\(|now_s\(|get_ticks\(", "time"),
       (r"\bSTATE\.\w+|getattr\(STATE", "STATE"),
       (r"_m\d_flow\.\w+|_flow\.\w+", "flow"),
       (r"(?<!\.)\brandom\.(?!Random\()\w+\(|_rng\.|rng_legacy|LEGACY_RNG", "random"),
       (r"special_flags|BLEND_", "blend"),
       (r"aaline|aacircle|aapolygon|gfxdraw\.aa", "aa"),
       (r"\bWIDTH\b|\bHEIGHT\b|get_width\(|get_height\(|get_rect\(", "window")]


def _func_nodes(tree):
    return {n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def dynamic_lines(modname: str, func: str, depth: int = 3):
    """Scan ``func`` and (transitively, same module) every helper it calls for dynamic inputs."""
    import importlib
    mod = importlib.import_module(modname)
    src = Path(mod.__file__).read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)
    lines = src.splitlines()
    funcs = _func_nodes(tree)
    if func not in funcs:
        raise SystemExit(f"{modname}.{func} not found")
    out, seen, queue = [], set(), [(func, 0)]
    while queue:
        name, d = queue.pop(0)
        if name in seen or name not in funcs:
            continue
        seen.add(name)
        node = funcs[name]
        for i in range(node.lineno, node.end_lineno + 1):
            l = lines[i - 1]
            tags = [t for pat, t in DYN if re.search(pat, l)]
            if tags:
                out.append((i, tags, l.strip(), name))
        if d < depth:
            for n in ast.walk(node):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in funcs and n.func.id != name:
                    queue.append((n.func.id, d + 1))
    return funcs[func], out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("module")
    ap.add_argument("func")
    ap.add_argument("--kwargs", default="{}", help="JSON kwargs passed to the painter (e.g. the static-only switch)")
    ap.add_argument("--map", default=None, help="map size in tiles WxH (default: module MAP_W/MAP_H or meta)")
    ap.add_argument("--tile", type=int, default=64)
    ap.add_argument("--window", default="1000x700")
    ap.add_argument("--pad", type=int, default=4)
    ap.add_argument("--cams", type=int, default=4, help="camera grid per axis for the parity probe")
    ap.add_argument("--out", help="write the baked layer PNG here")
    ap.add_argument("--screen-attr", default="screen")
    ap.add_argument("--also-redirect", default="", help="extra modules whose 'screen' global to redirect, comma-separated")
    args = ap.parse_args(argv)

    import importlib
    import pygame
    pygame.init()
    node, dyn = dynamic_lines(args.module, args.func)
    print(f"{args.module}.{args.func} L{node.lineno}-{node.end_lineno} ({node.end_lineno - node.lineno + 1} lines), "
          f"params {[a.arg for a in node.args.args]}")
    print("dynamic / window-dependent lines:" if dyn else "no dynamic inputs found by the scan")
    for i, tags, l, owner in dyn:
        via = "" if owner == args.func else f" (in {owner})"
        print(f"  {i:5d} [{','.join(tags)}] {l[:100]}{via}")

    from engine.assets import bake_camera_layer, layer_bounds, probe_layer
    mod = importlib.import_module(args.module)
    fn = getattr(mod, args.func)
    kw = json.loads(args.kwargs)
    redirect = [(mod, args.screen_attr)]
    for extra in filter(None, args.also_redirect.split(",")):
        redirect.append((importlib.import_module(extra), args.screen_attr))
    ww, wh = (int(v) for v in args.window.split("x"))
    if args.map:
        mw, mh = (int(v) for v in args.map.split("x"))
    else:
        meta = None
        for cand in (mod, importlib.import_module(args.module.rsplit(".", 1)[0] + ".meta")):
            if hasattr(cand, "MAP_W") and hasattr(cand, "MAP_H"):
                meta = cand
                break
        if meta is None:
            raise SystemExit("pass --map WxH")
        mw, mh = meta.MAP_W, meta.MAP_H
    world = (0, 0, mw * args.tile, mh * args.tile)

    def paint(cx, cy):
        fn(cx, cy, **kw)

    from engine.core import pin_wall, unpin_wall
    T0_MS = 123456
    pin_wall(ms=lambda: T0_MS, s=lambda: T0_MS / 1000.0)
    t0 = time.perf_counter()
    b = layer_bounds(paint, world_rect=world, tile=(ww, wh), redirect=redirect, pad=args.pad)
    if b is None:
        print("painter drew nothing inside the map rect")
        return 1
    print(f"bounds: ORIGIN = ({b.x}, {b.y})  SIZE = ({b.w}, {b.h})   [{time.perf_counter() - t0:.1f}s]")
    t0 = time.perf_counter()
    bstats = {}
    layer = bake_camera_layer(paint, size=(b.w, b.h), origin=(b.x, b.y), tile=(ww, wh), redirect=redirect, stats=bstats)
    if bstats.get("unrepresentable_px"):
        print(f"UNREPRESENTABLE: {bstats['unrepresentable_px']} px touched by special-flag blits over the live world -> split them out")
    print(f"baked {b.w}x{b.h} in {time.perf_counter() - t0:.1f}s")
    cams = []
    n = max(1, args.cams)
    for j in range(n):
        for i in range(n):
            cx = b.x - ww + 40 + int((b.w + ww - 80) * i / max(1, n - 1)) if n > 1 else b.x
            cy = b.y - wh + 40 + int((b.h + wh - 80) * j / max(1, n - 1)) if n > 1 else b.y
            cams.append((cx, cy))
    t0 = time.perf_counter()
    st = probe_layer(paint, layer, (b.x, b.y), cams=cams, tile=(ww, wh), redirect=redirect)
    verdict = "EXACT" if st["diff"] == 0 else ("rounding-level" if st["max_delta"] <= 3 else "DIFFERENT")
    print(f"parity vs live painter over {len(cams)} cams x 3 backgrounds: {st['diff']} / {st['pixels']} px differ, "
          f"max channel delta {st['max_delta']} -> {verdict}   [{time.perf_counter() - t0:.1f}s]")
    if st["diff"]:
        print(f"  worst: cam={st['worst'][0]} bg={st['worst'][1]} diff px={st['worst'][2]}")
    # second pass: live painter at another wall-clock instant vs the same bake -> frozen animation shows up here
    T1_MS = T0_MS + 377
    pin_wall(ms=lambda: T1_MS, s=lambda: T1_MS / 1000.0)
    st2 = probe_layer(paint, layer, (b.x, b.y), cams=cams[:: max(1, len(cams) // 4)], tile=(ww, wh), redirect=redirect,
                      backgrounds=((97, 101, 109),))
    unpin_wall()
    if st2["diff"] > st["diff"] * 0.34 + 0 and st2["max_delta"] > st["max_delta"]:
        print(f"TIME-DEPENDENT: {st2['diff']} px differ when the live painter runs 377 ms later (max delta {st2['max_delta']}) "
              f"-> those elements must stay live")
    else:
        print(f"time check: live painter 377 ms later still matches the bake (diff px {st2['diff']}, max delta {st2['max_delta']})")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(layer, args.out)
        print("wrote", args.out)
    return 0 if st["diff"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
