---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1000
---
# STATUS - first-try

> Read this FIRST when resuming. Last updated: 2026-10-26

---

## Done

M1 rework WP0-WP9a committed on branch `m1/rework` (not pushed). Plan:
`docs/MISSION1_REWORK_PLAN.md`; resume brief: `docs/M1_REWORK_HANDOFF.md`.
- Recent commits: WP6 88eb583 + fix 367e625, WP7 c4e082d, WP8 294628a, WP9a goldens
  4a9d983. Also an unrequested docs/tools commit ee93cdf.
- WP9b prepared, NOT committed:
  - Staged: `tests/replay/baseline_v2/m1.json`, `tests/replay/baseline_v2/m1.fields.json`,
    `tests/loop/baseline_v6/m1.json`, `assets/baked/m1/.bakeinfo.json`,
    `assets/baked/m1/world_static_0.png`, `docs/engine/evidence/phase6/d6_baseline.json`
    (m1 draw_sites 262 -> 309).
  - Unstaged: `src/missions/m1/m1_audio.py` (loads via `engine.assets.load_sound`),
    `docs/LORE.md`, `docs/engine/BUGS.md` (B-004, B-034), `.wolf/STATUS.md`,
    `docs/M1_REWORK_HANDOFF.md`.
- Clean-copy gate on that state: compileall OK, smoke OK, ae_level_check OK, golden verify
  390/0, replay m1 OK (30 snapshots), bake m1 OK.

## Next quest

1. Haiku is comparing `ae_ci` at base 6a8379c vs `m1/rework` HEAD to tell whether these
   reds are ours: api snapshot (+210 names), `tests.unit.test_gl_composite` (3 errors,
   `GLRenderer.stats`), replay m2-m5 divergence, main loop parity 1/7, mission0
   zero-engine-diff (91 files). Expected: pre-existing, not ours.
2. If only known/baseline reds: commit WP9b as "M1 rework WP9b: ..." with trailer
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Stage only the intended
   files; NOT `assets/voice/*_matches.txt`, `tools/dev_panel.py`, `tools/zip_project.py`,
   `HANDOFF.md`, `save_dataverify.json*`, `shots_wp*`.
   - Known reds, not ours: mission4_stage_transitions, mission4_cinematic_arrest,
     mission5_shadow_finale, mission5_harbour_art, boundaries lint, bake m2 stale.
3. User plays the real flow once (cd to `m1-rework`; `python acaristan.py`, or
   `--jump m1`; F9 exfil) and decides the merge to main. Nothing is pushed.

Open items for the user:
- Far/dark/still detection takes 5.2 s vs plan 3.6 s (formula kept).
- Calm-guard suspicion meter is faint on dark asphalt.
- Street patrol route and the shutter guards facing each other: not done.
- Q throws a brick in M1.
- `files_already` radio line plays after NOTEBOOK_INSPECT.
- House `w_C` stains are baked in; stockroom outer walls (row 11+) still use container panels.
- Volkov's escape still uses the large `draw_commander` figure.
- CIOCAN `SPEAKER_COLORS` is a placeholder (205,75,60).
- Bay-fire visual is unrendered in preview.
- Walking sim did not finish in a headless run holding D (cause unknown).
- Music `assets/music/m1_infiltrate.ogg` and `m1_combat.ogg` must be supplied by the user.
- BUGS B-034 has a stale sentence ("m1.inspect is no M1 pass") that conflicts with the
  new rework sentence.
- Files carry CRLF at HEAD (core.autocrlf); pre-existing.

## Context

- Worktree `E:/Code/Call of Acaristan/m1-rework`, branch `m1/rework` cut from 6a8379c.
- Main checkout `First try` (branch `cutscene-holds`) must not be touched.
- Gates run only in detached temp worktrees.
- Opus edits only; Haiku does reads, gates and commits. Haiku won't write the Opus
  trailer, so the main session amends/commits those.
- Older M6 work (top-down art pass uncommitted, intro rewrite ce849fe) lives in the main
  checkout; see `docs/worklog.md`.

```bash
python tools/smoke_test.py
python -m compileall -q src
python tools/ae_golden.py verify --kinds gameplay
```

References: `.wolf/cerebrum.md`, `.wolf/anatomy.md`, `.wolf/buglog.json`.
