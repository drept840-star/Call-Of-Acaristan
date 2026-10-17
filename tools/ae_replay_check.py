#!/usr/bin/env python3
"""RPE6 Phase 9 exit tool: engine-save snapshots reproduce replay state.

For one segment per mission (in baseline order) it verifies, in-process:

  (a) capture -> deliberate mutation (STATE fields + RNG draws) -> restore
      reproduces the captured snapshot bit-for-bit (``statehash`` equal);
  (b) capture -> 30 frames -> restore -> the same 30 frames again lands on
      the same oracle hash as the uninterrupted run (``ae_replay.snapshot``).

Pure check: AE REPLAY-CHECK: OK replaces any need to commit expectations;
gameplay determinism itself remains ``ae_replay.py``'s job.
"""
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ae_replay as R  # noqa: E402  (boots the headless game like check does)


def _run_frames(stream, start, count):
    for f, (held, mpos, fire) in enumerate(R.expand(stream)):
        if f < start:
            continue
        if f >= start + count:
            break
        R._clock["frame"] = f
        R._engine_clock().set_wall_elapsed(R._elapsed_ms())
        R._mouse["pos"] = mpos
        R._mouse["buttons"] = (fire, False, False)
        R.STATE.dt = R.DT
        R.gc.game_update(R.Keys(held))


def main() -> int:
    from core.state import STATE
    from game import save_adapter

    ok = True
    for seg, (starter, label) in R.SEGMENTS.items():
        t0 = time.perf_counter()
        try:
            R._clock["frame"] = 0
            R._engine_clock().set_wall_elapsed(R._elapsed_ms())
            random.seed(R.SEED)
            getattr(R.gc, starter)()
            random.seed(R.SEED)
            stream = R.make_stream(R.SEED + sum(map(ord, seg)), R.SECONDS * R.FPS)

            # Warm up 30 frames before capturing: lazy one-time systems
            # initialise on the first update (and draw RNG doing it); a
            # real checkpoint is captured mid-mission, past that point.
            _run_frames(stream, 0, 30)
            snap = save_adapter.capture()
            h0 = save_adapter.statehash(snap)
            # (a) mutation -> restore round-trip
            STATE.screen_shake = 99
            random.random(); random.random()
            from engine.core import LEGACY_RNG
            LEGACY_RNG.random()
            save_adapter.restore(snap)
            h_back = save_adapter.statehash()
            # (b) continue / restore / continue -> same oracle hash
            _run_frames(stream, 30, 30)
            h_first = R.snapshot()["hash"]
            save_adapter.restore(snap)
            _run_frames(stream, 30, 30)
            h_second = R.snapshot()["hash"]
            good = (h_back == h0) and (h_first == h_second)
            ok &= good
            print(f"{seg}: {'OK' if good else 'FAIL'}  hash={h0[:12]} "
                  f"a={'OK' if h_back == h0 else 'DIFF'} b={'OK' if h_first == h_second else 'DIFF'} "
                  f"({time.perf_counter() - t0:.1f}s) {label}", flush=True)
        except Exception as e:
            ok = False
            import traceback
            traceback.print_exc()
            print(f"{seg}: ERROR {e!r}", flush=True)
    print("AE REPLAY-CHECK: OK" if ok else "AE REPLAY-CHECK: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
