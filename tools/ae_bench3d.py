#!/usr/bin/env python3
"""AE BENCH3D - 3D frame budget bench (RPE6 Phase 11 exit evidence).

Times the two data-driven 3D scenes per quality tier (presets +
local lights + contact shadows + baked AO/cast shadows on): vasile's office wide
take and the Mission 0 depot outro, software backend, 1000x700.
Tier rows are named <scene> (tier 2), <scene>_q1, <scene>_q0 in
bench_budgets.json - the low-end profile evidence (P11).

    python3 tools/ae_bench3d.py                # record
    python3 tools/ae_bench3d.py --check-budget # verdict vs bench_budgets.json
                                               # (default set reference_win; ACA_BENCH_SET=owner
                                               # enforces the raw 6.22 budgets)

Each row runs ``--runs`` passes (default 1; on a quiet machine use
``--runs=3`` for a certification run) and the verdict uses the best pass:
the reference machine keeps working during CI, so with runs > 1 only the
fastest pass reports the code's own cost.
"""
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    surf = pygame.display.set_mode((1000, 700))
    from core.user_settings import SETTINGS
    from cutscenes import m5mid3d
    from missions import m0

    def office():
        m5mid3d._vasile_wide(surf, 1200)

    def depot():
        m0._draw_depot3d(surf, 1600)

    results = {}
    runs = 1
    frames = 60
    for a in sys.argv[1:]:
        if a.startswith("--runs="):
            runs = int(a.split("=", 1)[1])
        elif a.startswith("--frames="):
            frames = int(a.split("=", 1)[1])
    _q0 = SETTINGS.quality_3d
    try:
        for tier, suffix in ((2, ""), (1, "_q1"), (0, "_q0")):
            SETTINGS.quality_3d = tier
            for name, fn in (("office3d", office), ("depot3d", depot)):
                fn()  # warm caches at this tier (renderer resizes)
                best = None
                for run in range(runs):
                    samples = []
                    for _ in range(frames):
                        t0 = time.perf_counter()
                        fn()
                        samples.append((time.perf_counter() - t0) * 1000.0)
                    samples.sort()
                    stat = (statistics.mean(samples),
                            samples[min(len(samples) - 1, int(0.99 * len(samples)))])
                    if run:
                        print(f"AE BENCH3D: {name + suffix} run {run + 1}/{runs} "
                              f"avg={stat[0]:.2f} ms p99={stat[1]:.2f} ms")
                    if best is None or stat[0] < best[0]:
                        best = stat
                key = name + suffix
                results[key] = best
                passes = "1 pass" if runs == 1 else f"best of {runs} passes"
                print(f"AE BENCH3D: {key} avg={best[0]:.2f} ms "
                      f"p99={best[1]:.2f} ms "
                      f"({passes} x {frames} frames, software, quality {tier})")
    finally:
        SETTINGS.quality_3d = _q0

    if "--check-budget" in sys.argv:
        import json
        with open(os.path.join(ROOT, "tools", "bench_budgets.json"),
                  encoding="utf-8") as fh:
            caps_all = json.load(fh)["scenarios"]
        want = os.environ.get("ACA_BENCH_SET") or "reference_win"
        ok = True
        for name, (avg, p99) in results.items():
            if want == "owner":
                cap = caps_all[name]
                good = avg <= cap["budget_ms"]
                print(f"AE BENCH3D BUDGET {name}: {'OK' if good else 'FAIL'} "
                      f"(owner budget avg<={cap['budget_ms']} ms)")
            else:
                cap = caps_all[name][want]
                good = avg <= cap["avg_cap_ms"] and p99 <= cap["p99_cap_ms"]
                print(f"AE BENCH3D BUDGET {name}: {'OK' if good else 'FAIL'} "
                      f"({want} caps avg<={cap['avg_cap_ms']} p99<={cap['p99_cap_ms']}; "
                      f"6.22 budget {caps_all[name]['budget_ms']} ms)")
            ok = ok and good
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
