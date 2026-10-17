# ADR-006: Golden-image oracle — software backend, pinned clock, tolerances, storage
Status: accepted (oracle, tolerances, clock pin) · proposed (storage)
Date: 2026-10-11
Context: Phase 0 needs a reproducible parity oracle (§9). With `ACA_FREEZE=1` plus a per-shot `random.seed`, all 351 cutscene frames reproduced byte-identically, but 9 of 14 gameplay shots differed between runs. Pinning `pygame.time.get_ticks()` and `time.time()` made 14/14 identical, so gameplay draw code reads the wall clock (BUGS B-001). GL output can vary across drivers.
Decision:
- Oracle settings: `ACARISTAN_RENDERER=software`, 1000×700, seed 1337, `ACA_FREEZE=1`, `get_ticks` pinned to 100000 and `time.time` to 1.7e9 before game import (`tools/ae_golden.py`).
- Tolerances per §9: gameplay/UI exact; 3D cutscene ≤ 0.5 % of pixels with diff > 8 and mean ≤ 0.6; cross-backend governed by `engine3d_check`.
- Cutscene samples at 25/50/75 % of `max(min_ms, len(text)·28 + 900)`, rendered through the player composite (as `m5_gauntlet_cycle.py` does).
- The clock pin is a declared workaround, removed once the Phase 1 clock owns time. The baseline must stay identical when it is removed.
- Storage (proposed): commit `manifest.json` (sha256 per shot). PNGs (28.5 MB) go to Git LFS or are regenerated from the baseline commit. The owner decides.
Alternatives considered: grayscale signatures like `tools/golden.py` (too coarse for exact 2D parity; kept as a fast smoke check); GL as the oracle (driver variance).
Consequences: Wall-clock-driven effects can't be seen in goldens until B-001 is fixed. Re-baselining needs a CHANGELOG entry with before and after images.
Verification: `ae_golden.py verify` → 0 failures on an unchanged tree (achieved 2026-10-11, 365/365).
