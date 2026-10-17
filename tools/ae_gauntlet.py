#!/usr/bin/env python3
"""AE GAUNTLET - render everything once at offsets nobody tested.

RPE6 Phase 10 (M5). The golden set proves specific frames at
specific times; the gauntlet sweeps the *neighbourhood*:

  1. every shot of every data timeline, rendered at two fresh
     offsets (137 ms and duration-271 ms - never golden times),
     through cutscenes.draw_cutscene_scene;
  2. every mission's gameplay (replay segment starters) rendered
     for 30 frames on a shifted input stream (seed + 999).

Any exception is an S1 finding; a blank frame where a scene
renderer exists is an S2 finding. The report lands in
docs/engine/evidence/phase10/gauntlet.txt; exit 0 only if clean.

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
        python3 tools/ae_gauntlet.py
"""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import numpy as np
    import pygame
    import ae_replay as R  # boots pygame + game_core like the oracles

    screen = R.cfg.screen
    findings = []
    shots_n = 0

    # -- 1. every timeline shot at two fresh offsets -------------------
    from cutscenes import draw_cutscene_scene
    from game import timelines
    ids = sorted(f[: -len(".timeline.json")]
                 for f in os.listdir(timelines.TIMELINES_DIR)
                 if f.endswith(".timeline.json"))
    for tid in ids:
        try:
            shots = timelines.shots(tid, [])
        except Exception:
            findings.append(f"S1 timeline {tid}: shots() raised\n"
                            + traceback.format_exc(limit=3))
            continue
        for shot in shots:
            shots_n += 1
            dur = int(shot.get("duration_ms") or shot.get("dur") or 2000)
            for t in (137, max(138, dur - 271)):
                try:
                    draw_cutscene_scene(screen, dict(shot), t)
                except Exception:
                    findings.append(
                        f"S1 {tid}/{shot.get('id')} t={t}: render raised\n"
                        + traceback.format_exc(limit=3))
                    continue
                arr = pygame.surfarray.array3d(screen)
                if float(np.std(arr)) <= 1.0:
                    findings.append(
                        f"S2 {tid}/{shot.get('id')} t={t}: blank frame")

    # -- 2. gameplay on a shifted input stream --------------------------
    import core.game_core as gc
    for seg, starters in R.SEGMENTS.items():
        try:
            R._clock["frame"] = 0
            R._engine_clock().set_wall_elapsed(R._elapsed_ms())
            R.random.seed(R.SEED + 999)
            getattr(gc, starters[0])()
            R.random.seed(R.SEED + 999)
            stream = R.make_stream(R.SEED + 999, 30)
            cam = (0, 0)
            for f, (held, mpos, fire) in enumerate(R.expand(stream)):
                R._clock["frame"] = f
                R._engine_clock().set_wall_elapsed(R._elapsed_ms())
                R._mouse["pos"] = mpos
                R._mouse["buttons"] = (fire, False, False)
                from core.state import STATE
                STATE.dt = R.DT
                res = gc.game_update(R.Keys(held))
                if isinstance(res, (tuple, list)) and len(res) >= 2:
                    cam = (res[0], res[1])
                gc.game_draw(cam[0], cam[1])
        except Exception:
            findings.append(f"S1 gameplay {seg}: raised\n"
                            + traceback.format_exc(limit=3))

    out = os.path.join(ROOT, "docs", "engine", "evidence", "phase10")
    os.makedirs(out, exist_ok=True)
    verdict = "clean" if not findings else f"{len(findings)} finding(s)"
    lines = [f"AE GAUNTLET: {verdict} ({shots_n} shots x2 offsets, "
             f"{len(R.SEGMENTS)} gameplay segments x30 shifted frames)"]
    lines += findings
    text = "\n".join(lines) + "\n"
    with open(os.path.join(out, "gauntlet.txt"), "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write(text)
    print(lines[0])
    for f_ in findings[:10]:
        print(f_.splitlines()[0])
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
