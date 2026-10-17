#!/usr/bin/env python3
"""AE BENCH3D - 3D frame budget bench (RPE6 Phase 11 exit evidence).

Times the two data-driven 3D scenes per quality tier (presets +
local lights + contact shadows + baked AO/cast shadows on): vasile's office wide
take and the Mission 0 depot outro, software backend, 1000x700.
Tier rows are named <scene> (tier 2), <scene>_q1, <scene>_q0 in
bench_budgets.json - the low-end profile evidence (P11).

    python3 tools/ae_bench3d.py                # record
    python3 tools/ae_bench3d.py --check-budget # verdict vs bench_budgets.json
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
    _q0 = SETTINGS.quality_3d
    try:
        for tier, suffix in ((2, ""), (1, "_q1"), (0, "_q0")):
            SETTINGS.quality_3d = tier
            for name, fn in (("office3d", office), ("depot3d", depot)):
                fn()  # warm caches at this tier (renderer resizes)
                samples = []
                for _ in range(60):
                    t0 = time.perf_counter()
                    fn()
                    samples.append((time.perf_counter() - t0) * 1000.0)
                samples.sort()
                key = name + suffix
                results[key] = (statistics.mean(samples),
                                samples[min(len(samples) - 1,
                                            int(0.99 * len(samples)))])
                print(f"AE BENCH3D: {key} avg={results[key][0]:.2f} ms "
                      f"p99={results[key][1]:.2f} ms "
                      f"(60 frames, software, quality {tier})")
    finally:
        SETTINGS.quality_3d = _q0

    if "--check-budget" in sys.argv:
        import json
        with open(os.path.join(ROOT, "tools", "bench_budgets.json"),
                  encoding="utf-8") as fh:
            caps_all = json.load(fh)["scenarios"]
        ok = True
        for name, (avg, p99) in results.items():
            if os.environ.get("ACA_BENCH_SET") == "sandbox_linux":
                cap = caps_all[name]["sandbox_linux"]
                good = avg <= cap["avg_cap_ms"] and p99 <= cap["p99_cap_ms"]
                print(f"AE BENCH3D BUDGET {name}: {'OK' if good else 'FAIL'} "
                      f"(sandbox caps avg<={cap['avg_cap_ms']} p99<={cap['p99_cap_ms']})")
            else:
                cap = caps_all[name]
                good = avg <= cap["budget_ms"]
                print(f"AE BENCH3D BUDGET {name}: {'OK' if good else 'FAIL'} "
                      f"(owner budget avg<={cap['budget_ms']} ms)")
            ok = ok and good
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
