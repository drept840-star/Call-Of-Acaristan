#!/usr/bin/env python3
"""ae_bench.py - frame budget bench (RPE6 §6.22; Phase 6 exit evidence).

Scenario: M5 Lower Quarter, rain on, 6 guards alive, one fire zone - the §6.22 line
"Gameplay frame (M5 quarter, rain, 6 guards, fire FX), software 2D <= 10 ms
update+render at 1000x700". Boots the M5 quarter checkpoint like the replay oracle,
tops the guard count up to 6, adds a FireZone, then times full
``game_update`` + ``game_draw`` frames (headless dummy SDL - software renderer).

Prints ``AE BENCH: <avg> ms avg, <p99> ms p99 (budget 10 ms)`` and the verdict against
§6.22. Sandbox numbers are indicative only - the reference machine is the owner's
(§6.22); exit 0 unless ``--strict``.
"""
from __future__ import annotations

import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUDGET_MS = 10.0


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    strict = "--strict" in args
    frames = 240
    for a in args:
        if a.startswith("--frames="):
            frames = int(a.split("=", 1)[1])

    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "src"))
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import time
    import ae_replay as R  # noqa: E402  (boots pygame + config like the replay oracle)
    from core.state import STATE
    import game.render as _gr

    starter = R.SEGMENTS["m5"][0]
    R._clock["frame"] = 0
    R._engine_clock().set_wall_elapsed(R._elapsed_ms())
    R.random.seed(R.SEED)
    getattr(R.gc, starter)()
    R.random.seed(R.SEED)

    # scenario dressing: 6 guards, rain, one fire zone near the player
    from missions.m5 import world as m5w
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery
    n = 0
    while len(STATE.enemies) < 6 and n < 12:
        m5w._spawn_m5_guard(px + 140 + 40 * n, py + 60 + 30 * n, "guard", aware=True)
        n += 1
    from core import config as _cfg
    if not getattr(STATE, "rain_drops", None):
        STATE.rain_drops = [(_cfg._rng_legacy.randint(0, _cfg.WIDTH), _cfg._rng_legacy.randint(0, _cfg.HEIGHT),
                             _cfg._rng_legacy.randint(10, 19)) for _ in range(120)]
    from entities.weapons import FireZone
    STATE.fire_zones = [FireZone(px + 90, py + 40)]

    stream = R.make_stream(R.SEED + 5, frames)
    samples = []
    cam = (0, 0)
    f = 0
    for held, mpos, fire in R.expand(stream):
        if f >= frames:
            break
        R._clock["frame"] = f
        R._engine_clock().set_wall_elapsed(R._elapsed_ms())
        R._mouse["pos"] = mpos
        R._mouse["buttons"] = (fire, False, False)
        STATE.dt = R.DT
        t0 = time.perf_counter()
        res = R.gc.game_update(R.Keys(held))
        if isinstance(res, (tuple, list)) and len(res) >= 2:
            cam = (res[0], res[1])
        R.gc.game_draw(cam[0], cam[1])
        samples.append((time.perf_counter() - t0) * 1000.0)
        f += 1
    samples.sort()
    avg = statistics.mean(samples)
    p99 = samples[min(len(samples) - 1, int(0.99 * len(samples)))]
    st = _gr.last_stats().as_dict()
    verdict = "within budget" if avg <= BUDGET_MS else "OVER BUDGET (sandbox hardware - owner re-run decides)"
    print(f"AE BENCH: scenario m5-quarter/rain/6-guards/fire x{f} frames: avg={avg:.2f} ms p99={p99:.2f} ms "
          f"(budget {BUDGET_MS:.0f} ms) - {verdict}")
    print(f"AE BENCH: draw stats {st['draws']} custom={st['custom']} ui_passes={st['ui_passes']}")
    if "--check-budget" in args:
        # Verdict mode (RPE6 P10): caps from tools/bench_budgets.json.
        # ACA_BENCH_SET=sandbox_linux selects the recorded sandbox caps;
        # otherwise the 6.22 owner-machine budget (avg) is enforced.
        import json as _json
        with open(os.path.join(ROOT, "tools", "bench_budgets.json"),
                  encoding="utf-8") as fh:
            caps = _json.load(fh)["scenarios"]["m5-quarter"]
        if os.environ.get("ACA_BENCH_SET") == "sandbox_linux":
            cap = caps["sandbox_linux"]
            ok = avg <= cap["avg_cap_ms"] and p99 <= cap["p99_cap_ms"]
            print(f"AE BENCH BUDGET: {'OK' if ok else 'FAIL'} "
                  f"(sandbox_linux caps avg<={cap['avg_cap_ms']} ms "
                  f"p99<={cap['p99_cap_ms']} ms; owner budget "
                  f"{caps['budget_ms']:.0f} ms decides on the owner machine)")
        else:
            ok = avg <= caps["budget_ms"]
            print(f"AE BENCH BUDGET: {'OK' if ok else 'FAIL'} "
                  f"(owner budget avg<={caps['budget_ms']:.0f} ms)")
        return 0 if ok else 1
    return 1 if (strict and avg > BUDGET_MS) else 0


if __name__ == "__main__":
    sys.exit(main())
