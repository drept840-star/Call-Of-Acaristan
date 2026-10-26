---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1000
---
# STATUS — first-try

> Read this FIRST when resuming. Last updated: 2026-10-27

---

## Done (2026-10-27 M1 rework complete on this branch)

Branch `cutscene-holds`, merge `ef9302b`: WP8+WP9a+WP9b merged in from `m1/rework`
(its tip `1c9e8ac` is now fully contained here; that worktree has no further M1 work).
The M1 rework plan (`docs/MISSION1_REWORK_PLAN.md`) is executed WP0-WP9.

- What landed here with this merge: WP8 hard lights (`m1.hard_lights` LIGHTING pass,
  halos, flood/bay cones; soft lamp pushes removed from `LightBuffer`, grade kept),
  ambience bands (street rain+wind vs inside rain_inside/console hum/stockroom drips),
  `m1_audio` music hook (silent without `assets/music/m1_{infiltrate,combat}.ogg`);
  WP9a seeded rain + 13 m1 goldens; WP9b replay/loop/bake/D6 baselines + docs.
- Gates on the merge: compileall OK, smoke OK (3 new WP8 checks green),
  ae_level_check OK, golden 390/390, replay m1 OK, loop m1 OK, bake m1 OK.
- ae_ci reds are ALL pre-existing — proven by rerunning them at pre-merge `63839e2`
  (detached temp worktree) and at `m1/rework` tip: unit `test_gl_composite` 3x
  `GLRenderer.stats`, api snapshot +210, boundary lint 18, bake m2/m3 stale,
  replay m2-m5 divergence at t=1s, loop parity 1/7 (m1 is the 1), mission0
  engine-tree hash (91 files, fails on the branch too).
- Earlier on this branch: letterboxed presentation (`63839e2`, 1000x700 canvas +
  `present()`), MP version-skew refusal (`a5e5c98`), launcher/updater (`d1a833e`),
  M6 train viewmodel tint (`39b168d`), M6 top-down art pass (uncommitted work
  committed before the WP0-WP7 merge).

## Next

1. User plays the M1 flow once here (`python acaristan.py` or `--jump m1`; F9 exfil)
   and decides the merge to main. Nothing is pushed anywhere.
2. Optional M1 polish (user calls, all listed in `docs/M1_REWORK_HANDOFF.md`):
   street patrol + shutter guards facing each other; suspicion meter visibility;
   Volkov escape figure; CIOCAN speaker color; Q-brick binding; `files_already`
   timing; stockroom outer walls; supply the two music files.
3. M6 leftovers (see 2026-10-25 worklog): noman identity pass; `_mat_fill` tex3d;
   user review of the M6 intro shots.
4. Known pre-existing reds to sweep some day: ae_ci list above, smoke MP flakes
   (rerun once), `GLRenderer.stats` test errors.

## Context

- Main checkout `E:/Code/Call of Acaristan/First try` = `cutscene-holds` (this file).
  `E:/Code/Call of Acaristan/m1-rework` = `m1/rework`, tip fully merged; its
  untracked shots/saves/handoff noise stays untracked.
- Files carry CRLF at HEAD (core.autocrlf); pre-existing.
- Gates: `python tools/smoke_test.py` -> `SMOKE TEST: OK`; `python -m compileall -q src`;
  `python tools/ae_golden.py verify`; `python tools/ae_replay.py check --only m1`.

References: `.wolf/cerebrum.md`, `.wolf/anatomy.md`, `.wolf/buglog.json`.
