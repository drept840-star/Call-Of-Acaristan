---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1000
---
# STATUS — first-try

> Read this FIRST when resuming. Last updated: 2026-11-08

---

## Balaceanu VO caption mismatch fix (2026-11-08, uncommitted)

Owner: "the TTS doesn't match what Balaceanu is saying in the narration box".
Root cause: the 13 TTS takes in `assets/voice/Balaceanu/` were recorded OUT of
spreadsheet order, so `voice.py`'s length-based `_align()` heuristic shifted most
lines. The broadcast mast beat (VO_009 "The prisoner is contained...") was playing
the take that actually says VO_011 "They'll see your face, Biribel...". Verified by
transcribing every take (faster-whisper base.en, scratch since removed; transcripts
kept at `assets/voice/Balaceanu/_transcripts.json`). Fix = the system's intended
mechanism: renamed each take's .ogg+.wav to its canonical `VO_xxx` (explicit names
always win, bypassing the heuristic). 12 unique lines named; VO_014 shares VO_006's
text/take; the duplicate VO_002 retake (old `7_04PM`) moved to `_retakes/`. VO_007
"Cut the feed!" gained audio it never had. `balaceanu_matches.txt` rewritten with
the verified mapping (LF/UTF-8). No dialogue/manifest text edited (canon: never edit
a recorded line). All 13 captions resolve to the correct file at runtime; VO_009
decodes 12.19s. compileall OK, **SMOKE TEST: OK**. Pre-existing unrelated reds:
`ae_normalize` crashes on root `_tmp_assets.py` (syntax error, not ours); ae_ci reds.
Owner playtest: `python acaristan.py --dev-mission3-broadcast-transition`.

## M3 Broadcast bridge dead-space pass (2026-11-08, uncommitted)

Owner: "a lot of dead space in the background and missing floors". All fixes in
`src/cutscenes/m3broadcast3d.py` baked sets (+ road/exterior camera tilt, outdoor
fog matched to sky); no timeline, dialogue, blocking or map changes. Dock: full
side returns + ceiling + wall ribs/practicals, widened and dressed back wall
(bulkhead lamp + conduit + pipes) so the open shutter frames a lit surface, not
void. Road: wet verge ground plane beyond the barriers, scrolling side blocks at
the lamps' 16 m/s, a second fogged skyline row, brighter dash; camera tilts down.
Exterior: lit entrance apron + bollard walkway, perimeter wall with gate gap,
stepped left/right wings, distant skyline, roof antenna; camera target lowered so
the facade base meets visible ground. Corridor: ceiling slab on the beam tops.
A back-wall glow sprite bled through the closed shutter (slat gaps) and was
removed — the emissive lamp box is geometry-occluded and clean. 5 broadcast unit
tests pass (seek determinism + corridor framing intact), compileall OK, standalone
**SMOKE TEST: OK**, 40 frames/backend in `shots/m3_broadcast3d/{gl,software}/`.
This session CAN view images: contact sheets + key frames reviewed on both
backends, no voids/floats/bleed. Changed file LF/UTF-8/no-BOM. Owner playtest:
`python acaristan.py --dev-mission3-broadcast-transition` jumps straight to the
five-shot bridge. Full ae_ci not run (known pre-existing reds).

## Office and medical GLB scenery (2026-11-08, uncommitted)

User requested six unused assets integrated: Zarya/tall Soviet PCs, CRT/LCD,
medkit and pill bottle. New `tools/ae_import_workstation_props.py` bakes all
six into `src/game/content/meshes/`; node transforms, embedded texture colours,
metre scale, deterministic face budgets, transparent glare removal and tagged
screen faces. `game/scenery3d.py` caches shared props/workstations and live
screen-only meshes, with procedural fallbacks at scene owners.
M2 upload/evidence PCs; M3 Comms/Archives/Broadcast desks, guard consoles and
cell monitor; M5 HQ signup/armory monitors + medical bench; M7 shared farmhouse
porch chest; shared M1 pickup helper upgrades existing bandage pickups across
missions. No maps, collision, interaction state, dialogue or health rules changed.
21 targeted tests pass (six new scenery tests), compileall/diff check and scoped
UTF-8/LF pass. GL/software M3 and GL M5 captures plus M2 upload/M7 porch captures
in `shots/scenery_props/`. Image input is unavailable to this model: appearance
needs owner review. Full normalizer still stops at existing scratch syntax line
13. Standalone **SMOKE TEST: OK**. Full engine gate: compileall, API, import,
text/data/timeline, frame budgets, replay-check, flash, software determinism
and holds pass; known baseline failures include M4 entity attributes, W1/D6
ratchets, M5 audio channel mocks and existing M7 motorcycle raw image load,
stale bake/replay/loop/mission0 drift. **AE CI: FAIL** (343/393 golden
mismatches in the dirty tree; scenery changes also intentionally change images,
no golden baselines regenerated). Both standalone and CI smoke pass.

## M3 Kill Order sniper sightline (2026-11-07, uncommitted)

Owner reports a targeting line through the cover block and an invisible
sniper. `m3ko3d._marksman` drew both a persistent beam and firing tracer
with a painter-layered 3D line, which can overpaint the slab. The guard's
projection was entirely behind the foreground pillar (render-difference
probe: zero pixels). Removed BOTH lines, kept the brief muzzle + stone hits,
shifted guard right onto a clear mezzanine firing bay, opened its rail and
added a local practical. Guard now contributes ~2,000 software / 1,724 GL
contrast pixels around the upper body between flashes. New regression asserts
no targeting line at any beat and visible silhouette with the guard removed
from a comparison frame. 14 KO/hold unit tests, compileall and both backend
40-frame captures pass. Final standalone **SMOKE TEST: OK** after the
light was scoped to the PA shot; owner visual sign-off pending.

## M3 Kill Order staging follow-up (2026-11-07, uncommitted)

Owner still saw actors stare at the door and Balaceanu's PA shot read badly.
Root cause: the stair shot allowed advance at 2200 ms but Biribel crossed
at 5300 ms; the PA lens initially missed the entrance and the lobby shot
had no connected threshold. Now stair minimum is 5400 ms in the timeline
and fallback meta; the lens follows both through the open portal and they
scan separate flanks on hold. PA shot has a cutaway stair throat, open portal,
separate timed entrance-to-cover routes, a pan from entry to speaker/overwatch,
and security-bay alarm dressing. Recorded lines unchanged. Eight KO tests +
five hold tests pass, timeline round-trip and compileall pass; 40 final GL
captures and 40 earlier software captures generated. Final standalone
**SMOKE TEST: OK**. Visual sign-off still needs owner; this model cannot
inspect the image captures.

## M3 door orientation (2026-11-07, uncommitted)

Fixed `src/missions/m3/draw3d.py`: north-only axis inference rotated lower
leaves of vertical double doors by 90 degrees (Comms, Archives, Kill Order).
Now follows contiguous D runs to concrete jambs on both axes, preserving the
cell armory's two-column wall. No map, collision or gameplay changes.
Four regressions in `tests/unit/test_m3_door_orientation.py` pass, covering
all five maps, both sliding axes and cache rebinding; compileall and scoped
LF/UTF-8/diff checks pass. **SMOKE TEST: OK**. Whole normalizer still crashes on
an existing line-13 scratch syntax error; ae_ci refuses another live lock
(pid 39632); did not steal it. Other working-tree changes left untouched.

## M3 Kill Order 3D bridge (2026-11-07, uncommitted)

Approved plan implemented in `src/cutscenes/m3ko3d.py`, routed by m3ko registry
wrappers with illustrated disabled/error fallback. Four shots: one-way breach
at 1150 ms, tread-supported descent (Volkov leads, separate lanes), pillar
cover/mezzanine marksman (actual muzzle ray terminates on pillar), empty dock
preview with existing m3_van asset. Shared textured materials, PS2 grade and
practical lighting. No mission state mutation, new dialogue or map changes.
Silent charge auto-advances; all lenses hard-cut. Meta/timeline agree.
24 KO/M3/hold regressions pass; compileall OK; 36 GL/software captures in
`shots/m3_ko3d/`. Stair regression checks actual sole geometry against steps,
not just root height; renderer tests check deterministic seeking and framing.
Standalone **SMOKE TEST: OK**. Full CI ran: FAIL (M5 audio unit errors,
M7 raw asset load, boundary/component/render-queue ratchets, stale bake,
golden/replay/loop/mission0 drift); no KO unit failures. Timeline round-trip,
API, holds and software determinism pass. No unrelated rebaselines made.
Repo normalizer still fails on existing scratch syntax; KO files LF/UTF-8.
Visual sign-off pending (model cannot view captures). Playtest:
`python acaristan.py --dev-mission3-kill-order`.
Archives stays reverted; earlier Comms and Molotov changes preserved.

Owner playtest follow-up: stair portal had a solid rear wall and routes ended
short. Replaced with genuine open aperture, displaced door leaf, extended
landing/corridor and both walks through z=5.9 to z>7. PA shot now has approach
then kneel, separated cover positions, side-biased camera, visible loudspeaker,
clerk counters/wall bays and distinct exit light. Removed searching beam that
could pass through cover. 25 targeted regressions pass; compileall and 36
captures/backend OK. New tests forbid wall sealing the exit and assert actual
passage/approach. Follow-up **SMOKE TEST: OK**; visual sign-off remains pending.

## M3 Comms visual upgrade (2026-11-07, uncommitted)

User says m3-comms graphics fall short of other 3D films. Service set now
uses shared ps2mat textured concrete/steel instead of plain large faces.
Added baked wall ribs, piping, recessed vents, ceiling structure, drainage,
rack modules/meters/handles/wiring, relay keys/paper and a physical warm lamp.
Lower ambient, stronger source-based warm/cool lights, small depth-masked
practical halos; radio insert has corner guards, buttons and a top control.
Animation, cast wardrobe, timelines and reverted Archives remain unchanged.
18 staging/hold/Molotov tests pass; compileall OK; 44 captures/backend succeed.
New regression asserts baked detail, textured surfaces and emissive sources.
Changed files LF/UTF-8 clean. **SMOKE TEST: OK**. Full CI still locked by another
run; repo normalization still crashes on existing scratch syntax error.
Visual sign-off still needs owner: this model cannot inspect image inputs.

## M3 Archives conversion reverted (2026-11-07)

User requested revert of the latest Comms -> Archives 3D conversion. Restored
original live-map cinematic and pacing; removed new film/test and Archives
preview option. Earlier service/radio staging and ghost Molotov fix preserved.
Old preview captures are historical only. Kill Order/Broadcast not converted.

## M3 ghost Molotov fix (2026-11-07, uncommitted)

Shared `entities.weapons.handle_throw_bottle` now rejects MISSION3 before
inventory, aim, audio or projectile side effects. M3 has no flight update but
its 3D FX renders the shared projectile list; firearm-equipped players with
nonzero bottle inventory could create a stuck ghost. Both RMB and G use this
handler. Two regressions cover all M3 weapons and preserve M1/M2/M6 throws;
unit tests + compileall pass; standalone **SMOKE TEST: OK**.

## M3 in-mission 3D staging, first bridge (2026-11-07, uncommitted)

User requested a proper 3D staging pass on the between-stage films, not the
intro/outro. First slice is **cell block -> Comms only**. New
`src/cutscenes/m3staging.py` draws a shared concrete service/relay set with
four lenses: exit wide, radio-handoff two-shot, power-on insert, Comms dolly.
Prisoner wardrobe, K-9 right-hand carry, left-hand radio IK, planted-foot
walks, deterministic seek/holds. `m3ops.py` wraps the four existing registry
IDs; original 2D takes survive under `ACARISTAN_CUTSCENE3D=0` / render failure.
Dialogue/takes and mission hand-off unchanged. Timeline + meta fallback have
hard cuts and auto-advance/quiet UI on the two silent action shots.

Follow-up playtest fix: one-handed rifle is now lowered/outboard with a
20 cm minimum radio-hand/gun-AABB gap in tests. Volkov's toss/retract stays
on his right side; recovery keeps the held arm and blends his turn away.
The old target path could penetrate the chest even with safe IK (solver
returns least-bad pose for impossible targets). This M3 prop is a radio;
user also called it a Molotov, so a separate Molotov scene remains unconfirmed.

9 staging + 5 hold regressions pass (`python -m unittest
tests.unit.test_m3_staging tests.unit.test_hold -v`), compileall OK;
24 fresh frames/backend captured by
`python tools/m3_staging_preview.py --backend gl|software` into
`shots/m3_staging/{gl,software}/`. Fresh engine3d parity OK (worst 3.26%). Changed
files normalize cleanly; whole-repo normalizer crashes on the pre-existing
untracked `_tmp_assets.py:13`. Follow-up standalone smoke: **SMOKE TEST: OK**.
Follow-up ae_ci refused: another run holds its lock; not stolen.
Prior full ae_ci: **FAIL**, broad failures (M4 entity attributes,
shared->mission ratchet, M5 audio mock/channel IDs, M7 raw asset load,
golden/replay/bake/mission0 drift); do not rebaseline those in this task.

Radio-handoff follow-up (user disliked the take): replaced the 840 ms float
with a 360 ms ballistic toss, visible wind-up, delayed receiving reach and
220 ms catch absorption. Locked two-shot (no competing dolly), with projection
regressions keeping the radio body inside frame and >18 internal pixels tall.
15 staging/hold tests pass; compileall OK; standalone **SMOKE TEST: OK**;
44 fresh frames per backend captured.
Recorded dialogue, timeline and unrelated M6 edits unchanged. Full ae_ci still
refused its live lock; repository normalizer still hits the existing scratch
syntax error. Changed Python files verified LF/UTF-8 without BOM.

**Needs visual playtest:** this agent cannot view image inputs. Jump directly
with `python acaristan.py --dev-mission3-comms`. Archives, Kill Order and
Broadcast bridges have NOT been converted. Pre-existing M6 working-tree
edits were left alone.

---

## M7 goat-escape bridge (2026-10-31, branch `walk/look-pass`, uncommitted)

Chores-complete film, so Bodi's "one of them got out" is watched, not told:
`src/cutscenes/m7goat.py` (5 shots: pen / slip / orchard / two-shot / Bodi) +
`src/game/content/timelines/m7.goat.escape.timeline.json`. `farmyard._chores_complete()`
requests it once from the trough and generator handlers; `meta.MID_TIMELINES`
(`MID_GOAT_ESCAPE`) registers it, `flow.on_cutscene_done` resumes chores without
moving the ladder, and `flow.film_music` keeps the farm cue. VO_345-347 moved
from `GoatRescue.__init__` into the film; the cream goat is hidden from the pen
after it. Gates: compileall OK, smoke OK (new `m7_goat_escape`), M7 unit 29 OK,
AE TIMELINE/VALIDATE OK. Not hand-played yet.

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
