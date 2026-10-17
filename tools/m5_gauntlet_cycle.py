"""M5 visual gauntlet - one full cutscene render cycle at delivery resolution.

    python tools/m5_gauntlet_cycle.py CYCLE [cut] [c2d] [rm] [only=<substr>]

For every shot in the M5 shot lists (intro, mid, ending) renders, at WIDTH x HEIGHT
and through the real player composite (draw_cutscene_scene + vignette + scanlines +
letterbox + dialogue box):
  * 10 timestamps spread across the take + first/last 200 ms,
  * extra frames either side of every detected cut/impact (frame-diff spike on a
    100 ms scan),
  * an 8 x 16 ms burst strip at the busiest moment,
  * ms/frame (median of the scan).
c2d = 2D fallback pass (ACARISTAN_CUTSCENE3D=0 + draw_m5x_2d), rm = reduced motion.
Output: previews/m5_gauntlet/cycle_N/cutscenes/<shot>/... + _sheet_<pass>.jpg +
timing_<backend>.json.  Backend follows ACARISTAN_RENDERER (default gl).
"""
import json
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ACARISTAN_RENDERER", "gl")
os.environ["ACARISTAN_CUTSCENE3D"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()
from core import config as cfg  # noqa: E402
from core.config import WIDTH, HEIGHT  # noqa: E402
from core.state import STATE  # noqa: E402
from cutscenes import engine as eng  # noqa: E402
from cutscenes import m5martial3d as m3d  # noqa: E402
from cutscenes import m5mid3d as mid  # noqa: E402
from missions.m5 import meta  # noqa: E402

CYCLE = sys.argv[1] if len(sys.argv) > 1 else "1"
ARGS = sys.argv[2:]
WHAT = {a for a in ARGS if "=" not in a} or {"cut"}
ONLY = next((a.split("=", 1)[1] for a in ARGS if a.startswith("only=")), "")
BASE = os.path.join(ROOT, "previews", "m5_gauntlet", "cycle_" + CYCLE, "cutscenes")
CHAR_MS = 28          # ~typewriter speed (1 char / ~1.7 frames at 60 fps)
SCAN_MS = 100

# the takes' own authored lengths (tools/m5_shots.py); the player holds a shot
# >= min_ms and until the line is typed out, so the real length is the max.
DUR = {"m5_tv_bulletin": 6400, "m5_safehouse_tv": 7200, "m5_retardovici_tv": 7400,
       "m5_river_gate": 7200, "m5_ucilev_scope": 9200, "m5_ucilev_reveal": 8400,
       "m5_ucilev_leaves": 6800, "m5_radio": 8800}


def shot_list():
    out = []
    for lst_name, tag in (("mission5_intro_shots", "in"), ("M5_MID_CUTSCENES", "mid"),
                          ("mission5_ending_shots", "end")):
        v = getattr(meta, lst_name)
        shots = sum(v.values(), []) if isinstance(v, dict) else list(v)
        for i, s in enumerate(shots):
            if s.get("scene") == "title_card":
                continue
            out.append(("%s%02d_%s" % (tag, i, s["scene"]), s))
    keys = [k for k in ONLY.split(",") if k] or [""]
    return [o for o in out if any(k in o[0] for k in keys)]


def duration(s):
    txt = s.get("text") or ""
    return max(s.get("min_ms", 3000), DUR.get(s["scene"], 0), len(txt) * CHAR_MS + 900)


def composite(surf, s, t, mode):
    if mode == "c2d" and s["scene"].startswith("m5x_"):
        mid.draw_m5x_2d(s["scene"], surf, t)
    else:
        eng.draw_cutscene_scene(surf, s, t)
    cfg.draw_vignette(surf, strength=80 if s.get("quiet_ui") else 180)
    if not s.get("quiet_ui"):
        cfg.draw_scanlines(surf)
    cfg.draw_letterbox(surf)
    txt = s.get("text") or ""
    if t >= s.get("caption_after_ms", 0) and not s.get("hide_caption") and (txt or s.get("speaker")):
        ci = min(len(txt), max(0, t - s.get("caption_after_ms", 0)) // CHAR_MS)
        eng.draw_dialogue_box(surf, s.get("speaker"), txt, ci, len(txt), t >= s.get("min_ms", 0))


def small(surf):
    return pygame.transform.smoothscale(surf, (96, 67))


def diff(a, b):
    import pygame.surfarray as sa
    x, y = sa.array3d(a).astype("int32"), sa.array3d(b).astype("int32")
    return float(abs(x - y).mean())


def run(mode):
    surf = pygame.Surface((WIDTH, HEIGHT))
    takes = shot_list()
    tw, th = 250, 175
    cols = 12
    sheet = pygame.Surface((tw * cols, th * len(takes)))
    sheet.fill((20, 20, 24))
    font = pygame.font.SysFont("arial", 14)
    timing = {}
    for row, (name, s) in enumerate(takes):
        d = duration(s)
        out = os.path.join(BASE, mode, name)
        os.makedirs(out, exist_ok=True)
        # 1) 100 ms scan -> cut / impact spikes + ms/frame
        prev, scan, times = None, [], []
        for t in range(0, d + 1, SCAN_MS):
            t0 = time.perf_counter()
            composite(surf, s, t, mode)
            times.append((time.perf_counter() - t0) * 1000)
            sm = small(surf)
            if prev is not None:
                scan.append((diff(sm, prev), t))
            prev = sm
        times.sort()
        timing[name] = round(times[len(times) // 2], 1)
        ts = {int(d * k / 9) for k in range(10)} | {0, 100, 200, max(0, d - 200), max(0, d - 100), d}
        spikes = sorted(scan, reverse=True)[:4]
        med = sorted(v for v, _ in scan)[len(scan) // 2] if scan else 0
        for v, t in spikes:
            if v > max(6.0, med * 3):
                ts |= {max(0, t - 120), t - 50, t, t + 50}
        ts = sorted(x for x in ts if 0 <= x <= d)
        for col, t in enumerate(ts):
            composite(surf, s, t, mode)
            pygame.image.save(surf, os.path.join(out, "%s_%05d.png" % (name, t)))
            if col < cols:
                sheet.blit(pygame.transform.smoothscale(surf, (tw - 2, th - 2)), (col * tw + 1, row * th + 1))
        sheet.blit(font.render(name, True, (255, 220, 120)), (4, row * th + 2))
        # 2) burst at the busiest moment
        busy = max(scan)[1] if scan else d // 2
        b0 = max(0, min(d - 8 * 16, busy - 64))
        strip = pygame.Surface((WIDTH // 2 * 4, HEIGHT // 2 * 2))
        for i in range(8):
            composite(surf, s, b0 + i * 16, mode)
            strip.blit(pygame.transform.smoothscale(surf, (WIDTH // 2, HEIGHT // 2)),
                       ((i % 4) * WIDTH // 2, (i // 4) * HEIGHT // 2))
        pygame.image.save(strip, os.path.join(out, "_burst_%05d.jpg" % b0))
        print("%-5s %-30s %5d ms  %2d frames  %6.1f ms/f  spikes=%s" % (
            mode, name, d, len(ts), timing[name], [t for v, t in spikes if v > max(6.0, med * 3)]))
    pygame.image.save(sheet, os.path.join(BASE, "_sheet_%s.jpg" % mode))
    r, _b = m3d._rend()
    be = getattr(r, "backend", "?")
    with open(os.path.join(BASE, "timing_%s_%s.json" % (mode, be)), "w") as f:
        json.dump(timing, f, indent=1)
    print("backend", be, "failed", m3d._cache.get("failed"), m3d._cache.get("err"))


if "cut" in WHAT:
    run("cut")
if "rm" in WHAT:
    prev = getattr(STATE, "reduced_motion", False)
    STATE.reduced_motion = True
    try:
        run("rm")
    finally:
        STATE.reduced_motion = prev
if "c2d" in WHAT:
    os.environ["ACARISTAN_CUTSCENE3D"] = "0"
    run("c2d")
    os.environ["ACARISTAN_CUTSCENE3D"] = "1"
print("M5 GAUNTLET CYCLE %s DONE" % CYCLE)
