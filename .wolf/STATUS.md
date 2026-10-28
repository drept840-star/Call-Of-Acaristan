---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1000
---
# STATUS — first-try

> Read this FIRST when resuming. Last updated: 2026-10-27

---

## M7 playtest fixes (2026-10-28, branch `m7/fallow-ground`, uncommitted)

Owner playtest list fixed in place (details: Obsidian `Sessions/2026-10-28 Call of Acaristan - M7 playtest fixes.md`):
- Shots aim along the crosshair before the kick; 8 lanes incl. centre; hard FX (`raid3d.py`).
- Allies carry a rifle (`m6world3d.hum` "ally" branch); Alex picks firing spots, 13 m leash (`raid_brain.py`).
- Guards fall, dogs roll and stay (`raid_world.dog_fall`).
- Raid ground, sky and hills cleaned (`m7world3d.py`).
- Bridge: stage `raidin` and film `m7.raidin` between prep and raid.

Gates: smoke OK, compileall OK, unit 485 OK (full suite before the copy, M7 28 after), boundary OK. `ae_ci` was 20/26 before the copy; not re-run. Still red: API snapshot, asset bake, replay, loop parity, mission0 diff (uncommitted engine/asset/baseline edits). `m7runner.py` now copies the shotgun helpers in instead of importing `engine.anim.figure_kit`.
Open: hand playtest; truck gunner hidden by his own truck box.

## Mission 7 "Fallow Ground" (2026-10-28, branch `m7/fallow-ground`, uncommitted)

All seven beats are implemented and headless-tested: 3D drop-off film, top-down chores and
prep, 2D runner film, playable 3D raid (`src/missions/m7/raid3d.py` + `raid_*`), 3D burning-farm
finale, radio choice writing `STATE.m8_route`, outro. Details: `docs/worklog.md` (2026-10-28) and
the implementation notes at the end of `docs/MISSION7_PLOT.md`.

Gates green: compileall, smoke (`mission7_vertical_slice`), unit 479, ae_validate/text/hold/
mission0, boundaries (W1 baseline now 51). `ae_ci` red only on bake/replay/loop: replay hashes
all of `STATE`, so the new M7 fields shift every segment, and m1/m2 also differ in camera/player
from the uncommitted M1 work, so baselines were NOT re-recorded.

Next: playtest the raid by hand (dev jumps `m7*`); record Bodi/Alex takes (`VO_219`-`VO_227`);
persist `m7_preps`/raid checkpoint; settle the doc conflicts ("Tomorrow night" vs M8 "at dawn").

---

## Investigating (2026-10-27 M1 dropoff cutscene "replays" report)

User reports the m1.dropoff cut (street drop-off after the briefing) replays
("same 2-3 shots repeating"; user says the van truly re-pulls-out). Could NOT
reproduce in any deterministic config: real `_legacy_frame` loop headless with
scripted SPACE input (idle / spaced / 30 Hz mash) plays the cut exactly once;
shot clocks continuous (offsets 0/+4300/+6600 applied in engine.py line 23);
goldens `gp.m1.dropoff.*` match. `finish_briefing` is the only `start_cutscene`
caller; update+handle_event are gated by `not gsm.transitioning` (app.py
~4164/~4203) so it cannot double-fire. Diagnostics shipped: `ACA_CUTSCENE_TRACE=1`
appends `start_cutscene`/`player_state` (player replacement = restart, shot idx,
start_time) lines to `build/cutscene_trace.log` (app.py `_cut_trace`/`_cut_watch`;
NOT inside CutscenePlayer/_CutsceneState/finish_briefing — the smoke test execs
those in bare namespaces). Also real, non-replay issues in the take itself:
shots 2-3 share one static hold cam (goldens 01/02 near-identical stills),
SPACE blocked by min_ms holds (4300/2300/2500), painter clamps at 9100 ms.
Cause confirmed by frames (not a double start): shots 2 and 3 painted the same
static wide street frame (golden `gp.m1.dropoff.01.t50` vs `02.t50`), so the cut
read as one shot repeating. Working-tree fix (uncommitted): three scales, beat 1
wide pan, beat 2 `m1_dropoff_follow` 1.6x on Biribel, beat 3 `m1_dropoff_entry`
2.4x at the side door (draw.py `_draw_dropoff_zoom`). Smoke OK; dropoff goldens
recaptured. Open: user confirms the cut reads right in play.

## Done (2026-10-27 M1 Volkov art, uncommitted)

User: "in M1, Volkov is drawn uglily". `_draw_volkov_topdown` (missions/m1/draw.py)
hand-rolled him like Enemy.draw (rotated coat polygon + hair circle + cig splinter).
Now it blits the cached figure_kit cast body — `_volkov_body`, the M4/M5/M6 recipe
(3x supersample, smoothscale 84x84, artpack.pose per facing, scale 0.232 on 64 px
tiles), feet on his post/run line over the guard shadow, walk bob on the body only.
`_volkov_turn` + `STATE.volkov_draw_angle` deleted, plus the stale smoke reset line.
Frames: shots/m1_volkov/. Gates: compileall OK, smoke OK; no golden covers tile 15,27.

## Done (2026-10-27 respawn fix, uncommitted)

M1 "invisible player after respawn" fixed: die -> Retry left `death_anim_phase=2`
+ stale tilt armed because `m1.start_mission()` hand-rolls its reset (no
`STATE.reset()`). `death_anim.reset_stale_visuals()` added and called from
`m1.start_mission()` (`entities/death_anim.py`, `missions/m1/main.py`).
Gates: compileall OK, smoke OK, headless die->retry->move probe OK (probe
script deleted after use). Bug logged as bug-106 in `.wolf/buglog.json`.

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

## Done (2026-10-27 overnight CI sweep, uncommitted)

All seven pre-existing ae_ci reds from the list below are green on this
branch, verified with a full `python tools/ae_ci.py` (26 gates) + smoke.

- **B-041** (real defect, `docs/engine/BUGS.md`): context-free `GLRenderer`
  test construction had no `stats` dict once `_composite` wrote light stats;
  `SoftwareRenderer.__init__` now owns the shared `stats` dict. 6/6 tests.
- **E4 boundary lint 0**: `engine.ai.__init__` re-exports the
  bt/cover/senses/squad public names (B-021 pattern); call sites re-pointed
  in `m6/yard_brain.py`, `m6/yard_hud.py`, `ui/arena_view.py`,
  `engine3d/gl.py` to 2-level facades.
- **Stale oracles re-baselined** (content drift, proven by scratch-set
  self-reproduction first): api snapshot 616 names; `baseline_v2` replay
  m2–m5 (5/5); `baseline_v6` loop (7/7); bake m2/m3 rebaked (only
  `.bakeinfo.json` moved, art byte-identical).
- **mission0 pin re-frozen** `356f0326…` (91 files) for the Oct 21
  ai/collision subsystems, the Oct 26 MP/HUD sweep and today's facade —
  justified in `docs/engine/reports/phase10.md` ("2026-10-27 addendum").
- Smoke MP flakes: one extra standalone run — `SMOKE TEST: OK` (twice total:
  inside the CI run and standalone; the MP flakes did not reproduce today).
- Rule recorded in BUGS.md: re-run the oracle gates in the same session as
  any engine/public-surface change; stale oracles read as pre-existing reds.

Old list (fixed 2026-10-27): unit `test_gl_composite` 3x `GLRenderer.stats`,
api snapshot +210, boundary lint 18, bake m2/m3 stale, replay m2-m5 divergence,
loop parity 1/7, mission0 engine-tree hash.

## Context

- Main checkout `E:/Code/Call of Acaristan/First try` = `cutscene-holds` (this file).
  `E:/Code/Call of Acaristan/m1-rework` = `m1/rework`, tip fully merged; its
  untracked shots/saves/handoff noise stays untracked.
- Files carry CRLF at HEAD (core.autocrlf); pre-existing.
- Gates: `python tools/smoke_test.py` -> `SMOKE TEST: OK`; `python -m compileall -q src`;
  `python tools/ae_golden.py verify`; `python tools/ae_replay.py check --only m1`.

References: `.wolf/cerebrum.md`, `.wolf/anatomy.md`, `.wolf/buglog.json`.
