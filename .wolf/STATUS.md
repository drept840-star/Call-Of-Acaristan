---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1000
---
# STATUS — first-try

> Read this FIRST when resuming. Last updated: 2026-10-26

---

## Done (2026-10-26 M1 rework WP1: painter peel-off)

Branch `m1/rework`. `missions/m1/draw.py:submit_frame` now submits every M1 layer
(`m1.tiles` static bake on FLOOR, decor/doors/blood on DECALS_DYNAMIC, one
`CustomDraw` `m1.game_draw` for the actor block on ENTITIES, FX on FX_WORLD, HUD
`m1.hud`/overlays, light grade `m1.lighting` on DEBUG); `core/game_core.py` hosts M1
through the submitter path like M5. Pixel-equal: golden 379/379 (M1 subset 3/3) and a
9-state sha256 parity probe (start/desks/warehouse/combat/hotwire/death/alarm/exfil/
notebook). `ae_d6_gate`: m1 custom=1, direct draw sites 288 -> 262. B-034 updated.
Two parity-forced deviations from `docs/MISSION1_REWORK_PLAN.md` WP1 are recorded in
B-034: pre-actor FX and the hotwire panel stay below the floating text, and the light
composite stays above the UI (it grades the HUD too).
- Next: WP2 (escape cutscene as timeline) in the same plan; WP3+ follow.

## Done (2026-10-25 M6 top-down art pass, user signed off, NOT committed)

Customs, noman and rail now use the same art source as M4/M5. Brief: `docs/M6_TOPDOWN_ART_BRIEF.md`; detail is in `docs/worklog.md`.
- All floors come from the art pack (new `sn`/`st` snow tiles). Walls are painted as blocks by `_paint_wall`.
- No tex3d is left in floors, walls or roofs.
- Light: hard blooms, an M5-style torch, two-step searchlights with a rim, and `_COLD` floodlights.
- Gates: compile, smoke, 56 M6 tests and 34 gameplay goldens are green. Perf is within A/B noise.
- Shots: `shots/m6_td_after/contact_sheet.png`.
- Open: noman still reads paler and emptier than M5; new snow tiles plus watch posts would fix it, and that is the user's call. `_mat_fill` prop interiors still use tex3d.

## Done (2026-10-25 M6 intro rewrite, committed ce849fe)

Six new insertion shots (`meta.mission6_intro_shots`, `cutscenes/m6films.py`). The user has not reviewed them in-game yet. Older uncommitted work stays in the same files: the Whiteout rename, train audio `warm()`, the renderer cache, yard docs and the M6 fail-screen check. A clean HEAD fails `mission4_boot_and_walk` and the M3 `02_interrogation_room` goldens without the uncommitted M3/M4 story work.

## Earlier (details in `docs/worklog.md`, `docs/M6_3D_PERF.md`, `docs/FIXES_STORIES.md`)

- 2026-10-24 M6 3D frame-rate pass: median 32 -> 17 ms. Compare only interleaved A/B runs; this PC swings ~2x between runs.
- 2026-10-23 M6 top-down combat pass: exits lock until the Guards are dead, and Guards reuse M5 sprites.
- 2026-10-23 story consistency pass (M1-M6): cutscene and dialogue edits must go in both the `.timeline.json`/`.dlg.json` and the Python fallbacks. VO_198-204 are caption-only.

### Known pre-existing reds

- `ae_replay.py check`: m1-m5 diverge at t=1s.
- `ae_ci --quick`: the boundaries/api/d6/bake checks stay red; `GLRenderer.stats` composite tests error.
- Smoke flaked once on 2026-10-25 and passed 4 reruns; the cause was not captured.

---

## Next phase

1. Commit the M6 top-down art pass when the user asks: only `src/missions/m6/decor.py`, `stealth.py`, the art-pack tile additions and the docs.
2. Optional noman identity pass: new snow tiles and border watch posts.
3. User review of the M6 intro shots and the re-baked M3 cutscene frames.
4. Optional: record VO_198-204.

## Architecture (unchanged)

Python 3.13 + pygame-ce; in-house engine3d (GL 3.3 with software fallback). Runtime cutscene/dialogue data overrides the Python fallbacks (`ACA_TL_SRC=legacy` / `ACA_DLG_SRC=legacy`).

```bash
python tools/smoke_test.py
python -m unittest tests.unit.test_m6_campaign -q
python tools/ae_golden.py verify --kinds gameplay
```

References: `.wolf/cerebrum.md`, `.wolf/anatomy.md`, `.wolf/buglog.json`.
