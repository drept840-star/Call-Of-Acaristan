# Reference-machine reconciliation (2026-10-15) — Phase 4 pre-flight

Green restore after the 2026-10-14 23:51 merge, plus the oracle re-baseline on the
reference machine and the `ae_golden.py --only` fix (BUGS B-018). This closes the
"owner re-captures `tests/` on the reference machine" step of STATUS "Next three
steps" and the "sandbox baselines only" caveat of `reports/phase3.md`.

## What was red and why

The merge laid the session's file outputs over the owner's working copy: `src/` is the
owner's newer work, while the `tests/` oracles (unit tests, `tests/golden/baseline_v0`
hashes, loop `baseline_v4`) still described the pre-merge/session snapshot. All red
gates were reproduced identically under the canonical gate interpreter `.venv`
(Python 3.14.3, pygame-ce 2.5.7, SDL 2.32.10, numpy 2.5.1) and the system Python
(3.13.3, pygame-ce 2.5.5, SDL 2.32.6) — the drift is content, not machine rasterisation.

| Gate | Before | After |
|---|---|---|
| unit tests | 129 run, 2 failures + 4 errors | 136/136 |
| golden | 10 failures (373 shots) | 373/373 |
| main loop | 2/7 segments | 7/7 |
| W1 boundary edges | 52 | 48 (baseline) |
| smoke `mission5_sprites` | FAIL (path separators) | OK |

## The `--only` trap (B-018)

A filtered recapture renders only the matching specs, but gameplay shots inherit state
from earlier renders (M5 rain/fire FX). Recording `gp.m5.quarter_*` via `--only` and
then verifying failed on exactly those three shots (`max` <= 195, ~21k px): the
recorded hash described a state the full-sequence `verify` can never reproduce.
Fixed in `tools/ae_golden.py`: `--only` filters only what is recorded/compared; every
spec still renders. Post-fix, `capture --only gp.m5.quarter` reproduces the
full-capture hashes byte-for-byte.

## Re-baseline

- `tests/golden/baseline_v0`: full-sequence capture (373 shots, software renderer,
  seed 1337), `verify` 373/373. 14 hashes differed from the sandbox manifest; 10 were
  beyond tolerance vs the pre-merge baseline PNGs (`cut.m5...decree.t25/t50/t75`,
  `gp.m5.print_entry`, `gp.m5.quarter_start/mid/east`, `gp.m3.cell_a/b/c`). The
  objective-text change is proven in code (`src/missions/m5/flow.py` has only the new
  "north-east of the press hall" text); the rest are FX / layout / soft-light moves
  consistent with the merged work.
- `tests/loop/baseline_v5`: recorded on the reference machine, `check` 7/7. First-diff
  frames vs v4: boot 120 (MENU), m1 295, m2 5, m3 0, m5 1; walk/m4 byte-identical.
  v0-v4 are kept as history.
- Replay (5/5) and the API snapshot (±0) were already green and were not re-recorded.
- Full gate: `AE CI: OK` (10/10 implemented rows) — `ae_ci_final.log`.

## Files here

- `manifest_drift_report.txt` — three-manifest comparison, A (sandbox) vs B (partial
  recapture) vs C (full re-baseline).
- `compare_manifests.py` — the script that produced it (run from the repo root).
- `drift_heatmaps/` — the 20 `_verify` artifacts (`.diff.png` / `.now.png`) of the 10
  out-of-tolerance shots, from the verify run against the stale reference pair.
- Raw run logs (converted from PowerShell 5.1 UTF-16 to UTF-8/LF; contents verbatim,
  console noise included): `probe_out.txt` (determinism probe), `rebaseline_out.txt`
  (the discovery run), `golden_*_tmp/fixed/final.log`, `loop_*.log`, `smoke.log`,
  `unit_full.log`, `ae_ci_final.log`.
