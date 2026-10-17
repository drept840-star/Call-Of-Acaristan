# Retardovici Pulse Engine 6 Gold: STATUS

## Session 2026-10-14 (Arena sandbox) — plan of record
Environment: Linux sandbox, Python 3.13.16, pygame-ce 2.5.8 (SDL 2.32.10), numpy 2.3.5, **no moderngl** (software 3D only = the CI oracle), **no git**, repo at `/home/user/First try-slim`. Owner decisions: regenerate the oracle here (the slim archive has no `tests/`), track changes as files + changelog (no commits), close Phase 0 and Phase 1 this session, fix the 5 new W1 boundary edges properly (no ratchet).

Master prompt updated to v2 (`docs/engine/ENGINE_MASTER_PROMPT.md`): adds the §6.7 3D visual upgrade track, Phase 11, two risks, ADR-011..013. Phases 0–10 unchanged.
Phase 11 steps 1-4 DONE in sandbox 2026-10-16 (ADR-022, reports/phase11.md): lighting presets, local lights, contact shadows, baked AO; proof sheets previews/upgrades3d/. Steps 5-11 DONE same day (post-FX, weather, ADR-023 cast shadows, character polish, textures, animated props, ADR-024 mesh import) + low-end pass (render scale per quality tier, per-tier benches); AE CI OK - evidence/phase11/final_gate_steps5-11.txt, reports/phase11.md addendum.

| Milestone | Scope | Gate | State |
|---|---|---|---|
| M1 oracle + tooling | rewrite `tests/unit` (the originals are not in this archive); capture sandbox baselines (golden, replay, loop) and prove them reproducible; pin `PYTHONHASHSEED` in the harnesses and log the hash-order bug; remove the 5 new W1 edges (`audio.m5_finale → missions.m5.finale_script` ×4, `cutscenes.engine → cutscenes.m5shadow3d`) | `ae_ci.py`: every implemented row OK | **done** (`/tmp/ci_m1.txt`: 8/8 implemented rows OK) |
| M2 Phase 0 closeout | `.gitattributes`; LF/UTF-8 normalisation as one dedicated change set; B-003 mojibake comments; AST-equality proof per .py file; re-run `ae_audit.py`; Phase 0 report | smoke, golden verify, replay check, loop check identical before/after | **done** (`reports/phase0.md`, `reports/phase0_normalisation.txt`) |
| M3 Phase 1 closeout | B-002 (last global `random` sites, `GRAIN_VARIANTS` on a named stream); B-001 wall-clock reads through `engine.core` time (legacy loop feeds the clock; check tools pin the engine clock instead of pygame); B-011 re-examined; Phase 1 report | golden/replay bit-identical; loop bit-identical for the time migration, re-baselined (v2, ADR-005) for the grain stream; `ae_replay.py check` passes with an unpinned hash seed | **done** (`reports/phase1.md`; `/tmp/ci_m3.txt` `AE CI: OK`) |

**Phase 2 plan (Planning stage, 2026-10-14, after the asset diet + subtitle-timing fix):**

| Milestone | Scope | Gate | State |
|---|---|---|---|
| P2-M1 `engine.scene` kernel | `src/engine/scene/` (Scene, SceneStack: push/pop/replace/clear_to, overlay + passthrough semantics, deferred mutations during dispatch, trace on `log.channel("scene")`), unit tests, lint E1–E5 clean | unit + boundary lint | **done** (11 unit tests; lint 16 engine modules clean) |
| P2-M2 Legacy scene mirror | `GameStateManager.on_change` hook (`core/fsm.py`); `core/scene_mirror.py` (A-005); `_LegacyGameScene.stack`; loop probe records `scene_trace` and compares it when the baseline has it (v3 files gained the key additively); `tests/data/m5_scene_trace.txt` + `tests/unit/test_scene_mirror.py` | golden/replay/loop bit-identical (trace is additive) | **done** (`/tmp/ci_p2m1.txt`); open: a scripted end-to-end M5 playthrough driver so the trace comes from a real run, not the FSM flow |
| P2-M3 API snapshot | `tools/ae_api_snapshot.py` (`src/engine` public names → `tests/api/engine_api.json`, `check` mode) + CI row | `ae_ci.py` row OK | **done** (16 modules / 79 names; negative test caught a renamed method) |
| P2-M4 Take registry → CutsceneScene / InspectScene | (a) take registry generalised (58 branches → per-module registration, W1 169 → 114, golden 353/353); (b) `engine.scene.CutsceneScene`/`InspectScene` + A-007 mirrors (CUTSCENE[take], INSPECT[key]) | golden/replay/loop parity | **done** (`/tmp/ci_phase2.txt`) |
| P2-M5 Engine-ish shared modules | `render_util` → `engine.render2d`, `lighting` → `engine.lighting`, `artpack` + `sprite_lib` → `engine.assets`, `figure_kit` → `engine.anim`, deprecation shims at the old paths (A-006) | parity + lint | **done** (golden 353/353; `test_engine_shims.py`) |
| P2-M6 Ratchets + report | W1 ratchet 169 → 48 (facade trim + explicit mission take imports); replay `--only` fix deferred as B-013 (Phase 9); `reports/phase2.md`; ADR-014 | full `ae_ci.py` | **done** (`AE CI: OK`, 72 unit tests) |

Caveat: baselines captured here are machine-specific (fonts, SDL build). They are the oracle for this sandbox's before/after comparisons only and must not be copied over the owner's `tests/golden/baseline_v0`.

**Phase 3 plan (Planning stage, 2026-10-14, "Phase 3 in one shot + Phase 4 prep"):**

| Milestone | Scope | Gate | State |
|---|---|---|---|
| P3-M1 `engine.assets` pipeline | `manifest.py` (`ae.manifest/1`), `registry.py` (`AssetRegistry`: baked → render → fallback → placeholder, cache, ref-counts, `reload` + `AssetReloaded`), `bake.py` (deterministic bake, `.bakeinfo.json` source + pixel hashes, `--check` = hash + 10 % sample, lint: fringe/palette/light/text-fit, contact sheet), `watch.py` (`AssetWatcher`, stdlib polling), `loaders.py` (`load_image/load_sound/load_music`); `engine.anim.PoseCache`; `tools/ae_bake.py`; CI row live | `ae_bake --check --lint`, 20 unit tests | **done** |
| P3-M2 M5 pack migration | `src/art/m5` → `src/game/art/m5` + manifest/palette; baked files → `assets/baked/m5`; `art.m5` shim (A-008); `MISSION_RE` += `game.art.m\d`; smoke "every manifest entry resolves" | golden 353/353 bit-identical, 125 PNGs byte-identical on re-bake | **done** |
| P3-M3 census + D5 | `tools/ae_draw_audit.py` → `audit/draw_census.md`; 17 raw loads → `engine.assets.load_*` (D5 = 0, unit-guarded); pose LRU → `engine.anim` | full `ae_ci.py` (`/tmp/ci_phase3.txt`) | **done** |
| P3-M4 ≥ 80 % conversion M1–M4 | bake procedural dressing as `layer`/`sprite_def` packs per mission, re-baselined goldens per batch | golden before/after + CHANGELOG | **not started** (B-016; census ready) |
| P4-prep | `tools/ae_star_imports.py` → `audit/star_imports.md` (A-001); `tools/ae_hud_census.py` → `audit/hud_duplication.md`; hot-reload hook in `app.py` (`ACARISTAN_HOT_RELOAD=1`) | parity-neutral (docs/tools) | **done** |

---


Last updated: 2026-10-15 · Current phase: **8 exited in the sandbox 2026-10-15 (`reports/phase8.md`: 22 timelines + 1 production set render from data, golden 373/373, loop 7/7, replay OK; owner reference-machine `ae_ci.py` re-run pending). 7 exited in the sandbox 2026-10-15 (`reports/phase7.md`: 13 levels + 2 conversations load from validated data, golden 373/373, loop 7/7, replay OK; owner reference-machine `ae_ci.py` re-run pending). 6 exited in the sandbox 2026-10-15 (`reports/phase6.md`: D6 holds — `m5 custom=0`, others 4 ≤ 5; golden 373/373; §6.22 scenario 9.46 ms avg on the sandbox; owner reference-machine `ae_ci.py` re-run pending). Phase 5 exited in the sandbox (`reports/phase5.md`; owner re-run pending)** (**Phase 4 exited 2026-10-15** — `reports/phase4.md`: `engine.ui` + `engine.text` landed, string tables complete, no golden re-baselined; green restored on the reference machine 2026-10-15: goldens 373/373 + loop 7/7 re-baselined, `AE CI: OK` under `.venv`; B-018). **Phase 3 exited 2026-10-15** (`reports/phase3.md` + reference-machine addendum: bakes re-checked clean, `tests/` re-captured). **Phase 2 exited 2026-10-14** (`reports/phase2.md`, caveat: the scene stack mirrors the FSM until Phase 4). **Phase 0 exited 2026-10-14** (`reports/phase0.md`); **Phase 1 exited 2026-10-14** (`reports/phase1.md`).

**Caveat first:** everything RPE6 wrote is uncommitted (no git in the sandbox; the owner merges files). Baselines in `tests/` are now captured on the reference machine (2026-10-15: golden `baseline_v0` full recapture 373/373, loop `baseline_v5` 7/7; replay + API snapshot verified unchanged), so they are the oracle for this machine; sandbox-era loop sets v0–v4 are kept as history.

## Resume here
0. Sandbox only: `tests/golden/sandbox_linux/RECAPTURE.txt` — re-record the machine-local golden set before the first edit (10 s).
1. Read this file, then `AUDIT.md`, then master prompt §4 and §8.
2. Continue from the first unchecked box below.

## Phase 0 exit criteria
- [x] AUDIT.md complete, with counts. Evidence: `docs/engine/AUDIT.md` and `docs/engine/audit/*.md` from `python tools/ae_audit.py` (prints `AE AUDIT: OK`).
- [x] Golden baseline captured. `tests/golden/baseline_v0/`: 365 shots (351 cutscene frames = 117 shots × 25/50/75 %, plus 14 gameplay), with a manifest.
- [x] Golden baseline reproducible. `python tools/ae_golden.py verify` → `verified 365 shots ...: 0 failures, 0 errors`, byte-identical.
- [x] Replay baseline captured and reproducible. `python tools/ae_replay.py check` → m1..m5 `OK 30 snapshots match`. These are scripted-input segments; see caveats.
- [x] Line endings normalised in one dedicated change set (2026-10-14): `tools/ae_normalize.py --mojibake --apply` (90 files, 46 .py, AST-identical proofs), `.gitattributes` added. Gate identical before/after (`reports/phase0.md`). Owner: on the real repo run `git add --renormalize .` after copying `.gitattributes`.
- [x] All tests green after RPE6 changes. `python tools/smoke_test.py` → `SMOKE TEST: OK`; `python -m compileall -q src` → exit 0.
- [x] Docs scaffold: STATUS, AUDIT, BUGS, ADAPTERS, `adr/ADR-000-template.md`, ADR-001, ADR-002, ADR-003, and ADR-006 (golden tolerances, written early because Phase 0 needed it).

## Phase 1 exit criteria
- [x] `src/engine/core`: clock, rng streams, events, log, services, settings, profiling, errors/crash report, mathx, App. Stdlib-only, no import side effects (`tools/ae_import_check.py`).
- [x] Unit tests: `tests/unit/` has 43 tests (clock identity at 30/60/144 fps vs legacy `FixedStepClock`, wall clock + timebase pin hook, rng, events, crash report, boot, settings, services, log, mathx).
- [x] `tools/check_boundaries.py` (E1–E5 enforced for engine code; W1 shared→mission held at 169).
- [x] `tools/ae_ci.py`: one command. Every implemented row is OK (see the latest run below); later phases show as TODO.
- [x] ADR-004 fixed timestep.
- [x] Display ownership: `App.boot` owns `pygame.init`/`set_mode`/caption via ADAPTER A-001 and chooses `SDL_VIDEODRIVER` once at boot (no import-time setdefaults in `src/`). Caveat carried to Phase 4: boot still happens at `core.config` import time because 51 modules star-import `screen` (B-007).
- [x] Main-loop oracle: `tools/ae_loop.py` runs the real `app.py` loop headless (7 segments: boot/menu, M1–M5, walk; 4,020 frames) and hashes every frame. It's deterministic run to run after pinning the clocks and hash seed, neutralising B-008 and faking the mixer in game time.
- [x] Legacy loop hosted by the engine: `App.run_scene(_LegacyGameScene())` (A-002). The loop oracle is bit-identical before and after.
- [x] Simulation randomness through named rng streams (B-002) and wall-clock reads through the clock (B-001), keeping the golden and replay baselines identical. Evidence: 0 direct `random.X(` calls in `src/`; legacy stream adopted as `legacy`, grain on `grain`; 211 wall-clock reads → `engine.core.now_ms/now_s` (A-004); golden 353/353, replay 5/5 identical; loop identical for the time migration, `baseline_v2` for the grain stream (ADR-005). `AE_NO_HASHSEED_PIN=1 PYTHONHASHSEED=7 python tools/ae_replay.py check` → OK (B-011 withdrawn).
- [x] Crash report works: `tests/unit/test_errors.py` (`write_crash_report`), exercised by `App.run_scene` (A-002).

## Blocked / needs the owner
1. **Commit or stash the in-progress cleanup** (PDFs/, TXTs/, `__pycache__`, ... deletions; `.gitignore` and `AGENTS.md` edits). After that, run the normalisation commit:
   ```
   git add .gitattributes
   git add --renormalize .
   git commit -m "RPE6 P0: normalise line endings (LF), mark binaries"
   python tools/smoke_test.py ; python tools/ae_golden.py verify ; python tools/ae_replay.py check
   ```
   Among Python files, 31 change content (3 mixed, 28 CRLF; see AUDIT §2). Non-Python text files were not audited, so expect a few more (AGENTS.md is CRLF). `.gitattributes` is drafted at `docs/engine/gitattributes.proposed`.
2. **Golden image storage (ADR-006):** applied in the sandbox copy on 2026-10-14 (owner asked to trim the project): `tests/golden/baseline_v0/` holds `manifest.json` only (sha256 per shot); the 353 PNGs were deleted (−28 MB). `ae_golden.py verify` still passes from the hashes; heat-maps need PNGs, which `ae_golden.py capture` regenerates. On the owner's machine the same rule applies: commit the manifest, keep PNGs local or in LFS.
3. Optional: record one human-played 30–60 s segment per mission with `ACA_RECORD_INPUT=<file>.json python acaristan.py`, to complement the scripted streams.

## RPE6 changes so far (all uncommitted)
| File | Kind | Behaviour change |
|---|---|---|
| `tools/ae_audit.py` | new, read-only static audit | none |
| `tools/ae_golden.py` | new, golden capture/verify (§9) | none |
| `tools/ae_replay.py` | new, replay record/check (D8 seed) | none |
| `src/tools/input_recorder.py` | new, dev-only, off unless `ACA_RECORD_INPUT` is set | none (inert by default) |
| `src/app.py` | +11 lines: guarded import and a one-line `record()` hook before `gc.game_update` | none when the flag is unset. Smoke test green after the change |
| `docs/engine/**`, `tests/golden/baseline_v0/**`, `tests/replay/baseline_v0/**` | docs and baselines | none |
| `src/engine/**` (12 modules) | new engine core | none (new code) |
| `tests/unit/**` | new unit tests | none |
| `tools/check_boundaries.py`, `tools/ae_import_check.py`, `tools/ae_ci.py` | new gates | none |
| `src/core/config.py` | `set_mode` + caption replaced by `App().boot(force_mode=True)` (A-001) | none. Golden 365/365 identical, replay 5/5, smoke OK |
| `src/app.py` | resize paths also call `config._engine_app.set_screen()` | none |
| `src/app.py` | `while running:` → `def _legacy_frame()` + `_LegacyGameScene` + `run_scene` (A-002), done by script `build/ae_loop/wrap_loop.py` | none. `ae_loop` 4,020/4,020 frames identical. A crash report is now written on an uncaught error (additive) |
| `tools/ae_loop.py` | new main-loop parity probe + CI gate | none |
| `src/missions/m2/draw.py` | B-008 fix: `import random as _rng` → `_rng = random.Random()` (+3 comment lines) | The global RNG is no longer re-seeded from OS entropy, so seeded runs become reproducible. Visuals are identical: golden 365/365 and replay 5/5 unchanged. Loop baseline re-recorded as v1 (reason in BUGS B-008) |

## Definition-of-done tracker (D1–D12)
| # | State | Note |
|---|---|---|
| D1 boundary | not started | Baseline: 169 shared → mission edges |
| D2 Mission 0 | not started | |
| D3 scenes | not started | Baseline: `gsm` FSM in `app.py`; 251+35+24+9+3 shared refs to mission-named STATE fields |
| D4 entities | **done (sandbox)** | 32 `getattr(_private, default)` sites → 0; mission-prefixed stuffing 76 → 0 (`tools/ae_d4_gate.py` in CI); every `STATE` gameplay object is an entity with declared components via A-010; logic still legacy-hosted (ADR-016) |
| D5 assets | **partial** | 7 + 10 raw loads → **0** outside `engine/assets` (unit-guarded); registry + manifest + bake hashes live for the m5 pack; other packs (artpack sheets, fonts, sounds) still outside the manifest model |
| D6 render queue | not started | Baseline: 1,113 mission `pygame.draw(screen, …)` calls; per-function census `audit/draw_census.md` (M1–M4 3,992 call sites, 0.7–1.9 % converted; B-016) |
| D7 data content | not started | |
| D8 determinism | **partial** | Replay and loop oracles pass; game code reads time from the engine clock and randomness from named streams (`legacy`, `grain`). Still one shared `legacy` stream for all missions (per-system streams with Phase 5); harness pins kept as belt and braces |
| D9 tooling | not started | |
| D10 one-command CI | **partial** | `python tools/ae_ci.py`: 13 rows OK (asset bake check + lint live since Phase 3; string tables + text fit added in Phase 4), 4 TODO for later phases |
| D11 docs | started | Phase 0–3 reports, ADR-001..006, 014, 015, CHANGELOG through Phase 3, audits (draw census, star imports, HUD duplication) |
| D12 performance | not started | Reference machine recorded below |

## Reference machine (for §6.22 budgets)
i7-12700KF · 32 GB RAM · AMD Radeon RX 7800 XT · Windows 11 Pro. Canonical gate interpreter: `.venv` — Python 3.14.3 · pygame-ce 2.5.7 (SDL 2.32.10) · numpy 2.5.1 (SDL matches the sandbox's 2.32.10). The system Python (3.13.3 · pygame-ce 2.5.5 (SDL 2.32.6) · numpy 2.2.6) produced identical oracle hashes in the 2026-10-15 reconciliation, so either runs the gates; use `.venv`.

## Risk register (§11, deltas)
| Risk | Status |
|---|---|
| Mixed line endings breaking edit tools | **Closed** 2026-10-14: all text files LF/UTF-8 (`.gitattributes`); owner runs `git add --renormalize .` |
| Parity drift in ECS migration | Mitigation in place: replay baselines exist before Phase 5 |
| Golden oracle hides wall-clock effects | **Mitigated** (M3): game code reads `engine.core.now_ms/now_s`; the harness pins the engine clock explicitly. Remaining OS-clock readers (`src/net`, `src/tools`, save timestamps) are outside the oracles |
| Trailer tools broken in this copy | **New (asset diet).** `sfx_wav/`, `assets/voice/Trailer/`, `assets/music/trailer/` were deleted at the owner's request (game never loads them); `tools/trailer3d/*`, `build_sfx_stem.py`, `render_trailer_v2.py`, `mp_trailer_*` need them restored from the owner's disk |
| Frozen game clock in harnesses | **New (M3).** Tools that render without running the frame loop see a constant `now_ms()` (boot origin). Tools that need moving time must `pin_wall` or `feed_wall` (six check tools updated); a tool mixing `pygame.time.get_ticks()` arithmetic with game-time fields will mis-compute (the death-screen capture did) |
| Repo bloat from golden PNGs | **New.** 28.5 MB; ADR-006 storage decision pending |


## Phase 10 plan (Planning stage, 2026-10-16, Arena sandbox) - Tooling polish, docs, Mission 0, final gate
Master scope (§7 Phase 10 + §6.19/6.20/6.21/6.24 + §13): debug overlay/console/inspector complete;
timeline and level editors; `ae_new_mission.py` scaffolder; "add a mission" tutorial, then Mission 0
built by following it literally; benches, packaging, final docs. Exit = §13 final acceptance.
Facts: `tools/ae_timeline_edit.py` (CLI editor, round-trip proven P8) and `tools/dev_panel.py`
(jump launcher) exist; there is no in-game debug overlay/console/inspector, no scaffolder, no
Mission 0, no `ae_validate.py`/`ae_package.py`; CI still carries TODO rows engine3d-parity /
bench-budgets / mission-0. Subsystem docs: only `subsystems/ui.md` + `subsystems/text.md` exist.
Reference machine for budgets = the owner's dev machine (sandbox numbers are recorded as such).
Scope calls: (1) dev tools are game-side (`src/game/devtools.py`), toggled by F3/F4/`~`, inert
unless opened - harnesses never open them, so parity is untouched; the engine kernels stay pure.
(2) Editors write data files only: the level viewer + timeline scrub/nudge/save panels ride the
devtools overlay and reuse `game.levels`/`game.timelines` + `ae_timeline_edit`'s writer; the CLI
timeline editor remains the batch tool. (3) Mission 0 is a thin game-side host
(`src/missions/m0/`) over data in `src/game/content/{levels,dialogue,timelines,sets}/mission0.*`,
two enemy types as world prefabs, HUD plate from `engine.ui.std`, started via `--dev-mission0`;
zero edits under `src/engine/` during its construction, proven by an engine-tree hash recorded
in `tools/ae_mission0_check.py`'s manifest. (4) The engine3d parity CI row verifies the software
backend (double-render determinism + golden-frame diff on the M2 film) in the sandbox; the GL
diff itself stays an owner-machine run, stated plainly in the report. (5) B-038: the owner's
`golden/baseline_v0` in this tree is sandbox-flavoured (see BUGS.md/CHANGELOG); sandbox gates use
`sandbox_linux` as in every prior phase.

| Milestone | Scope | Gate | Est. |
|---|---|---|---|
| P10-M0 Oracles | recapture sandbox golden/loop sets | golden 373/373 (sandbox_linux) | done (B-038 logged) |
| P10-M1 Debug tools | `game/devtools.py`: F3 overlay (frame graph, RenderStats, entity count, scene stack), console (`~`: scene/seed/heat/golden/bench/reload/events subset), click inspector (component dump + edit of plain fields), collision view | unit tests for console commands + overlay data builders; golden/loop untouched | 2 blocks |
| P10-M2 Editors | devtools panels: level viewer (layers/triggers/spawns, reload) + timeline panel (scrub, key list, nudge, save to `.timeline.json`) | editor write round-trip unit tests; data validators still OK | 1-2 blocks |
| P10-M3 Mission 0 | `tools/ae_new_mission.py` scaffolder; `docs/engine/tutorial_add_mission.md`; build Mission 0 literally from it (level, 2 enemy types, dialogue, 3D cutscene, inspect shot, HUD plate); `tools/ae_mission0_check.py` (headless start-to-finish + zero-engine-diff hash) | ae_mission0_check OK; CI row replaces TODO | **done** (AE MISSION0 OK, engine sha unchanged) |
| P10-M4 Validation/bench/parity/packaging | `tools/ae_validate.py` data row; bench budget verdict row; engine3d parity row (software evidence, GL owner-deferred); `tools/ae_package.py` | CI rows OK | **done** |
| P10-M5 Docs + gauntlet | `docs/engine/ARCHITECTURE.md` + subsystem pages for all kernels; `tools/ae_gauntlet.py` (every cutscene shot at two new t values + gameplay shots; S1/S2 scan) + run | docs exist; gauntlet report clean | **done** (gauntlet clean: 92 shots x2, 5 segments x30) |
| P10-M6 Final gate | ADR-021, `reports/phase10.md` with D1-D12 evidence table, full `ae_ci.py` | `AE CI: OK (implemented gates)` | **done** (`evidence/phase10/final_gate.txt`, 26/26 rows, 0 TODO) |

## Phase 9 plan (Planning stage, 2026-10-15, Arena sandbox) — Save/load, determinism, settings, accessibility
Facts: saves exist (`core/save_system.py` campaign slots in `save_data.json`, atomic via `core/json_store`);
settings exist as a flat JSON dict (`core/settings_store.py`: defaults + `_normalize`) pushed into
`core/user_settings.SETTINGS` (converted floats) and a few `STATE` flags by `app.py`; accessibility today is
one bool (`reduced_motion`) honoured by the cutscene FX and the M2 gc-flash. Input is a raw
`pygame.key.get_pressed()` snapshot indexed by `pygame.K_*` constants at hundreds of sites; the app already
computes one effective snapshot (`keys_eff`) per frame and the loop harness records inputs. No gamepad code.
Scope calls: (1) kernels first (`engine.settings` typed layered schema, `engine.save` snapshot + statehash,
`engine.input` action map) with the legacy stores as clients - file formats and public APIs unchanged;
(2) accessibility lands as three *live* settings with parity-safe defaults: `shake_scale`
(gameplay shake chokepoint in `core/camera.py` + cutscene handheld in `m5fx3d.set_cam`), `flash_reduction`
(alpha cap at the full-screen white-flash sites; verified on the M5 breach golden frames), `text_speed`
(typewriter rates; default 1.0 = parity); (3) rebinding + gamepad work by *remapping the one pressed-state
snapshot* in `app.py` before the game sees it - zero call-site changes, identity by default;
(4) save snapshots (`ae.save/1`) are captured at M5 checkpoints next to the legacy save (capture + restore of
mission vars/RNG/frame; the respawn flow stays authoritative) and determinism is proven by
`tools/ae_replay_check.py` (D8: one segment per mission, state hashes every 60 steps, two-run equality).

| Milestone | Scope | Gate | Est. |
|---|---|---|---|
| P9-M0 Oracles | recapture sandbox golden/loop sets | golden 373/373 before edits | - |
| P9-M1 `engine.settings` kernel | typed schema (sections, types, ranges, enums), layering defaults < file < env, coercion, change listeners | unit tests, API snapshot | 1 block |
| P9-M2 `engine.save` + statehash | `ae.save/1` snapshot model/serialize vs a host dict protocol; `statehash` (sorted components, floats quantised 1e-4) | unit tests | 1 block |
| P9-M3 Settings adoption | `settings_store._normalize` on the engine schema (+ `shake_scale`/`flash_reduction`/`text_speed` keys), SettingsChanged push into `user_settings`/`STATE`; live shake + handheld scale; flash caps; typewriter speed | golden/loop parity at defaults; flash tool at enabled | 2 blocks |
| P9-M4 Save snapshots + D8 | `game/save_adapter.py` captures `ae.save/1` at M5 checkpoints; `tools/ae_replay_check.py` (record/check, one segment per mission) + CI row | replay check OK; golden/loop | 2 blocks |
| P9-M5 Input | `engine.input` action map (bindings persisted in settings), pressed-state remapping + joystick merge in `app.py`; settings screen shows bindings (read-only rows if UI cost grows) | loop 7/7 (inputs unchanged), unit tests | 2 blocks |
| P9-M6 CI + report | CI rows (replay_check, flash), ADR-020, `reports/phase9.md`, BUGS for leftovers | `ae_ci.py` OK | - |

**Phase 9 EXITED in the sandbox (2026-10-16):** kernels `engine.settings` /
`engine.save` / `engine.input` (9 kernel+adapter unit tests in
`tests/unit/test_engine_settings_save_input.py` of 271 total); adoption
P9-M3..M5 landed with parity-exact defaults - golden 373/373, loop 7/7,
replay OK, `AE REPLAY-CHECK: OK` (5/5), `AE FLASH: OK` (244.5 -> <=198.7 vs
cap 210), smoke OK, AE TEXT OK; CI rows `replaycheck` + `flash` added.
ADR-020, `reports/phase9.md`. Nothing re-baselined. Owner-machine
`ae_ci.py` rerun pending as usual.

## Phase 8 plan (Planning stage, 2026-10-15, Arena sandbox) — Declarative 3D sets and cutscene timelines
Facts: cutscenes are shot dicts (`{scene, speaker, text, lighting, min_ms, ...}`) in mission `meta.py`
lists (~19 lists) + `cutscenes/engine.py` cutscene1/2, played by `app.CutscenePlayer` (typewriter,
letterbox, vignette, grain) through `cutscenes.engine.draw_cutscene_scene` (a big 2D elif chain) plus
takes registered by id in `core.cutscene_registry` (m3ko/m3ops/m3broadcast/m3ending/m3cell/chair/
m4aftermath/m5martial3d/m5 finale). The 3D takes (`m5mid3d.draw_m5x`, `m5martial3d`) build
`engine3d` meshes imperatively per frame with a renderer pool + failure latch in `cutscenes/m5mid3d`.
Scope calls (repo over §3, strangler rules): (1) the sequencing layer migrates fully - every shot list
becomes an `ae.timeline/1` file and `game.timelines.shots()` feeds the existing player; (2) the M4
timed radio/arrest ladders (Phase 7 rescope) become timeline event tracks; (3) `engine.render3d`
gains the `ae.set3d/1` model + expression evaluator + data->primitive builder, and ONE production
3D set renders from data through a game-side bridge (proof of the declarative path); the remaining
imperative takes stay as registered FX hooks by id, documented in ADAPTERS.md (master exit allows
exactly this); a recorder-based keyframe migration of all 30 M5 shots is future work, not this phase;
(4) `engine.scene.CutsceneScene` learns to play a Timeline behind its existing surface (its own
docstring promised this in Phase 2).

| Milestone | Scope | Gate | Est. |
|---|---|---|---|
| P8-M0 Oracles | recapture sandbox golden/loop sets | golden 373/373 before edits | **done** |
| P8-M1 `engine.timeline` kernel | `ae.timeline/1` model + validator, safe expression evaluator (no `eval`), deterministic `TimelinePlayer` (keys/clips sampled at any t: camera/light/fx/dialogue/caption/audio/event + shot clips) | unit tests, API snapshot | **done** |
| P8-M2 `engine.render3d` kernel | `ae.set3d/1` model + validator + builder to an ordered primitive list (box/quad/quad_xz/decal+fallback/sprite3d/light/fog/repeat/prop_ref, expressions vs params) - pure data, no renderer imports | unit tests | **done** |
| P8-M3 Shot-list timelines | exporter: all `*_shots` lists -> `src/game/content/timelines/*.timeline.json`; `game.timelines.shots()` flip at definitions (`ACA_TL_SRC=legacy` fallback); `tools/ae_timeline_check.py` data == legacy | golden 373/373 + loop | **done** (20 lists, 90 shots) |
| P8-M4 Timed ladders | M4 `_M4_STORY_BEATS`/`_M4_ARREST_BEATS` -> timeline event tracks, sampled in `m4/flow.py` | loop m4 segment, golden | **done** |
| P8-M5 set3d pilot | one M5 3D set as `.set3d.json` + `game/render3d_bridge.py` (pool, failure latch, present; primitives via `engine3d`) rendering in production | golden cut shots for that scene | **done, rescoped**: bridge = apply-through-host-helpers (the pool/latch/present already live in `m5martial3d._rend/_present` and were not duplicated); pilot set = Vasile's office, 15/15 golden shots from data |
| P8-M6 Editor + CI + report | camera-key round-trip tool (`tools/ae_timeline_edit.py`: open, move key, save, reload, sample differs exactly), validator rows in `ae_ci.py`, ADR-019, ADAPTERS entries for hosted takes, `reports/phase8.md` | `ae_ci.py` OK | **done** (`reports/phase8.md`) |

## Phase 7 plan (Planning stage, 2026-10-15, Arena sandbox) — Data-driven levels and dialogue
Facts: `engine.level` / `engine.dialogue` do not exist yet. Every mission grid is produced at import by a
generator or builder (M1 MapBuilder, M2 `world.py`, M3/M4/M5 `_generate_*_map()`), then consumed as `list[str]`
(the standing runtime contract - unchanged). Markers (P/E/doors) ride inside the grid strings. Dialogue lives
as Python tables (`_M5_MARU_BEATS`, `_M4_*_BEATS`, radio queues, barks) plus cutscene scripts (Phase 8 owns takes).
Scope calls: (1) level JSON carries grids + marker-derived objects + stage metadata; patrol/trigger *logic*
stays code (it is behaviour, not placement), patrol *paths* are exported where they exist as literal tables;
(2) dialogue extraction covers gameplay dialogue tables now; cutscene dialogue rides Phase 8 timelines;
(3) every grid flip keeps the generator as an env-selected fallback (`ACA_LEVEL_SRC=legacy`) until the
validator has compared JSON vs generator row-for-row in CI - then data is the default and the fallback is the ticket.

| Milestone | Scope | Gate | Est. |
|---|---|---|---|
| P7-M0 Oracles | recapture sandbox golden/loop sets | golden 373/373 before edits | **done** |
| P7-M1 `engine.level` kernel | `.level.json` load/validate (tile layers, objects, triggers, paths, lights, decor, procedural_decor, metadata), Tiled `.tmj` importer | unit tests, API snapshot | **done** (6 kernel tests) |
| P7-M2 Exporter | `tools/ae_level_export.py`: import each mission, read final grids, write `src/game/content/levels/*.level.json` (+ objects from markers) | `tools/ae_level_check.py` JSON==generator | **done** (13 levels, per-mission marker maps) |
| P7-M3 Grid flip | M1, M5, M3, M4, M2 grids load from JSON at import (one gate per mission; runtime stays `list[str]`) | golden 373/373 + loop per mission | **done** (golden 373/373, loop 7/7, replay OK) |
| P7-M4 `engine.dialogue` | `.dlg.json` model (nodes, choices, conditions as data strings, effects), `DialogueRunner` (drives a sink, skippable), validator `tools/ae_dialogue_check.py` (unreachable, missing speakers/keys, fit via engine.text metrics where available) | unit tests | **done** |
| P7-M5 Dialogue extraction | M5 + M4 beat tables -> `content/dialogue/*.dlg.json`, loaded at runtime; exporter for reproducibility | golden/loop, validator clean | **done** (2 conversations; see rescope note) |
| P7-M6 CI + report | validator rows in `ae_ci.py`, ADR-018, `reports/phase7.md`, CHANGELOG, BUGS for leftovers | `ae_ci.py` OK | **done** (`reports/phase7.md`) |

Rescope note (2026-10-15): the timed ladders `_M4_STORY_BEATS` / `_M4_ARREST_BEATS` are
frame-scheduled event sequences, not conversations - they move with the Phase 8 timeline
work. P7-M5 covers the two conversation tables (`m5.maru`, `m4.liaison`). Data mode also
fixes a latent quirk: M4's choice splice mutated the shared module-level table under
legacy mode (one-shot per run, unchanged there).

## Phase 6 plan (Planning stage, 2026-10-15, Arena sandbox) — Render2D queue, camera, static layers, lighting, post-FX
Facts that shape the plan: `missions/m5/draw.py:game_draw` is a 30-step sequence with **state mutations inside the draw** (blood-decal fade +
removal, `muzzle_flash_timer -= 1`) and an **authored draw order** (corpses → pickups → quarter props → enemies → NPCs → Maru → player → mags; not
y-sorted); the M5 golden shots call `missions.m5.draw.game_draw` directly, the M1–M4 shots go through `core.game_core.game_draw`; the camera
(follow + shake + kick) is computed inside each mission's `game_update` and returned as `(cx, cy)`; `engine.render2d` holds only Phase-1 utilities.
Rules: one golden/loop gate per peel-off step; authored order is kept with explicit sort keys (y-sort is opt-in); draw-time mutations stay at
the same point of the frame (inside the drawable or at submit time, never moved across another reader); no new STATE fields.

| Milestone | Scope | Gate | Est. |
|---|---|---|---|
| P6-M0 Oracles | recapture sandbox golden/loop sets (deleted for quota); harness hygiene: M5 golden shots through `gc.game_draw` (verify identical first) | golden 373/373 before any `src/` edit | **done** |
| P6-M1 Kernel | `engine.render2d`: `queue.py` (layer table §6.6, `RenderQueue.submit/flush/stats`, drawables `SpriteDraw/SurfaceDraw/RotatedSpriteDraw(bucket cache)/TextDraw/PolyDraw/LineDraw/CustomDraw`), `camera.py` (`Camera2D`: follow/deadzone/bounds/shake trauma/zoom, `world_to_screen`), `static.py` (`StaticLayers`: chunked bake from a painter callback, signature invalidation), `postfx.py` (vignette/grain/flash/letterbox cached) | unit tests, API snapshot, BOUNDARIES 0 | 5 h |
| P6-M2 Host | `src/game/render/` facade (queue + camera owner); `core.game_core.game_draw` → one `CustomDraw` per mission on layer 4 + `RENDER_SUBMIT` systems + flush; `tools/ae_d6_gate.py` (per-mission census of screen draws + custom-draw stats, ratchet) | golden/loop parity by construction; D6 metric baseline (5 custom draws) | 3 h |
| P6-M3 M5 peel-off | (a) floor tiles → `StaticLayers` layer 0; (b) `decor.draw_under` → layer 1 if state-free; (c) decals/corpses/pickups/Maru/player/mags → sprite drawables, authored keys, layer 4; (d) guards → `GuardRenderSystem` (`RotatedSpriteDraw`, generalised bucket cache); (e) muzzle/bullets/particles/casings/fire zones/floating texts → layer 5; (f) vignette/rain/scanlines/flash → PostFX; (g) HUD/dialogue/reticle/death/FPV → layer 8 widget draws. One golden gate per letter; anything left as `CustomDraw` gets a BUGS ticket | M5 custom draws 1 → 0 (target), golden 373/373 each step, loop 7/7 | 12–14 h |
| P6-M4 Camera2D | mirror first (fed from legacy `cx, cy`), then the follow/shake math moves into `Camera2D` with identical formulas | loop 7/7, replay 5/5 | **done** (math in `engine.render2d.camera`, state flip deferred B-036) |
| P6-M5 Lighting | `LightSource` component + `LightingSystem` feeding `engine.lighting` (M5 lamps as data), `lighting.sample(x, y)` for the stealth readout where it exists | golden parity | **done, re-scoped** (`LightMapDraw` adopted; no component/`sample()` — no consumer, ADR-017 §6) |
| P6-M6 Report | ADR-017 (queue, authored order, static-layer contract, mutation-in-draw policy), `reports/phase6.md`, CI rows (D6 gate, draw stats), CHANGELOG | `ae_ci.py` OK | **done** (full gate green, `evidence/phase6/m3_m5_gate.txt`; owner `ae_ci.py` re-run pending) |
Total ≈ 29–31 h. Exit (§7): D6 holds (zero custom draws in M5 gameplay; ≤ 5 documented custom draws elsewhere — M1–M4 hosts, each with a ticket), golden parity, gameplay budget met (bench rows record only; budget gate is Phase 10).

## Phase 5 plan (Planning stage, 2026-10-15, Arena sandbox) — World/ECS-lite and standard systems

Oracles in this sandbox: `ACA_GOLDEN_SET=sandbox_linux` / `ACA_LOOP_SET=sandbox_linux` (captured 2026-10-15 from the
owner's Phase-4-exit tree before any Phase 5 edit; 373 shots, 7 loop segments). The owner's `baseline_v0` / `baseline_v5`
stay untouched; replay (state hashes) and the API snapshot are machine-independent and shared.

| Milestone | Scope | Gate | State |
|---|---|---|---|
| P5-M1 Sandbox oracles | env-selectable golden/loop sets, capture, verify | golden 373/373, loop 7/7, replay 5/5 | **done** |
| P5-M2 `engine.world` kernel | `component.py` registry (+schema/to_dict/from_dict), `entity.py` World (per-type dicts, spawn-order queries, deferred despawn, views, dump), `system.py` phases PRE/SIM/POST/RENDER_SUBMIT + Scheduler (order, read-only RENDER_SUBMIT guard in debug), `prefab.py` (`ae.prefab/1`, `extends`, diff), `std.py` (Transform, Velocity, Collider, Health, Faction, Tags, Label, Sprite, WalkCycle, HitFlash, AIBrain, Lifetime, LegacyRef; `slots=True`) | `tests/unit/test_engine_world.py` 17, boundaries, API snapshot (additive) | **done** |
| P5-M3 Legacy bridge | `game/world/legacy.py` views over `Enemy`/`Player`/pickup records/`Corpse`/`FireZone`/Maru dict + `LegacyRoster` PRE sync; `game/world/__init__.py` owner (install/pre_update/post_update/render_submit); host in `core.game_core.game_update`/`game_draw`; `tools/ae_dump_components.py` | replay 5/5, golden, loop, smoke, units | in progress |
| P5-M4 D4 for M5 | `missions/m5/components.py` `M5Guard` (10 fields) replaces the `m5_*` attributes (37 sites in m5 `quarter/world/draw/systems` via `_m5g(e) = game.world.ensure(e, M5Guard)`); `Enemy` role flags / `sight_mul` / `_dt_mul` declared (class-level defaults, see B-029); `_walk_prev/_walk_ph` → `WalkCycle.advance()` (the Enemy's declared `walk` is the entity's component); `game.world.entity_of/get/ensure` + `LegacyRoster.register_now/check_reset` (reset = `STATE.enemies` rebind; removed enemies tagged `removed`, kept until reset); `Player.story_outfit/_outfit_rk` declared; `m3/systems.py` `hasattr(e, "_apply_move")` dropped; grep gate `tools/ae_d4_gate.py` (hard rule + ratchet, baseline `evidence/phase5/d4_baseline.json`: m3_ 57 / m4_ 8 / is_missionN_ 11 → 0 by exit); replay snapshot v2 + `baseline_v1` (B-029) | replay 5/5 (v1) + compat proof 150/150 (v0), golden 373/373, loop 7/7, smoke OK, units 204, BOUNDARIES OK, AE API OK (53 modules / 320 names recorded), `AE D4: OK (hard=0, remaining 76)` | **done** |
| P5-M5 D4 for M3/M4/M2 | `missions/m3/components.py` `M3Guard` (13 fields incl. `ipa`, `shield_angle_width`), `missions/m4/components.py` `M4Guard`, `missions/m2/components.py` `M2Role`; enemy type + spawn label (`m3_type/m3_label`, `m4_type/m4_label`) → shared `engine.world.Label` (`kind`/`text`) so `entities/corpse.py` reads it mission-agnostically; 75 sites codemodded (`_mNg(e)`/`_mNl(e)` helpers, enemy receivers only, per-site defaults verified); smoke self-checks + `src/tools/ko_playability_audit.py` updated; roster reset made selective (B-030); `ae_d4_gate.py` ratchet 76 → **0** | compat proof 150/150 vs owner `baseline_v0` (`evidence/phase5/m5_replay_compat.txt`), replay `baseline_v1` re-recorded (m2/m3 `~world` grew), golden 373/373 (sandbox recapture; vs owner set the same 8 known cross-machine ids), loop 7/7, smoke OK, units 204, BOUNDARIES OK (W1 48 =), AE BAKE OK (4 manifests re-hashed after the rename, 246 PNGs byte-identical) | **done** |
| P5-M5b D4 for doors / arena | `M3Door` (10 fields) on `core.interactions.Door` entities (38 sites; roster `_spawn_door` + `STATE.doors` sync); `ui/arena_view.py` `_PoseMeta` replaces `Player._arena_{look,weapon,state,reload,reload_total,muzzle}`; `ae_replay` `~world` covers doors; `ae_d4_gate.py` ratchet over any non-STATE receiver; 2 new bridge unit tests (door survives an enemy-list swap; list swap keeps listed objects) | compat proof 150/150 vs owner `baseline_v0` (`evidence/phase5/m5b_replay_compat.txt`; m3 tracks 49 components incl. 33 doors), `baseline_v1` re-recorded, golden 373/373, loop 7/7, smoke OK, units 206, BOUNDARIES OK, AE D4 OK (0) | **done** |
| P5-M6 Hosted SIM | `game.world.step(fn)` runs the mission dispatcher as the declared SIM system `legacy_mission_update` (order 0) between the PRE roster sync and the POST flush (`LegacyMissionSystem`, `core/game_core.game_update`); `WalkCycle` kept render-driven, `Lifetime/HitFlash` systems and prefab adoption deliberately deferred (ADR-016 §5–7); 2 unit tests (phase order + exception path) | replay OK, golden 373/373, loop 7/7, smoke OK, units 208, BOUNDARIES OK (W1 48 =), AE D4 OK, compat OK vs `baseline_v1` and owner `baseline_v0` (`evidence/phase5/m6_gate.txt`), `evidence/phase5/m5_dump.txt` | **done** |
| P5-M7 Report + CI | `reports/phase5.md`, `adr/ADR-016-legacy-world-bridge.md`, ADAPTERS A-010, CHANGELOG Phase 5 entry, `ae_ci.py` rows D4 gate + component dump | `ae_ci.py --quick` OK (10 implemented rows) | **done** |
| P5-M6 Systems | `WalkCycleSystem` (POST), `LifetimeSystem` for fire zones, `HitFlash`; interaction/pickup hosting where separable; prefabs for M5 guards (`content/prefabs/`) | parity + dump tool | |
| P5-M7 Report | `reports/phase5.md`, ADR-016 (ECS-lite + views), CHANGELOG, API snapshot | full `ae_ci.py` | |

Honest scope note: `Enemy.update()` interleaves AI, movement, collision and shooting per enemy; splitting it into
per-system passes changes RNG/interaction order and breaks replay parity, so movement/collision/combat stay inside the
legacy update (hosted as the SIM authority) in this phase — the systems that move are the separable ones listed in P5-M6.

## Next three steps
0. **(done) P5-M5b — D4 for doors + arena sprites**: `M3Door` component (10 fields) replaced the `door.m3_*` attributes on `core.interactions.Door`
   (38 sites); the roster registers `STATE.doors` (`_spawn_door`: `Label(kind="door")`, `Collider`, Transform over `rect`); `ui/arena_view.py` keeps the
   posed sprite's state in `_PoseMeta` beside the sprite instead of `Player._arena_*`; replay `~world` now covers doors; D4 gate ratchet = any non-STATE
   receiver, hard rule includes `v`. Next real step: **P5-M6**.
1. **(done) P5-M5 — D4 for M3/M4/M2** (`m3_*` 57 sites: `missions/m3/{world,systems,sweep,draw,__init__}.py`, `entities/corpse.py:196`,
   `src/tools/ko_playability_audit.py`; `m4_*` 8; `is_mission2_*`/`is_mission3_ipa` 11; `shield_angle_width`; `core/interactions.py:573`;
   `core/level_editor.py:153`): one `components.py` per mission, `_mNg(e)` helper, same codemod discipline (enemy receivers only), per-mission
   `ae_replay.py check` + `ae_loop.py check --seg mN`, `ae_d4_gate.py --update` after each mission (ratchet down only).
2. **(done, re-scoped) P5-M6 — systems**: hosted SIM (`LegacyMissionSystem`); `WalkCycleSystem`/`LifetimeSystem`/`HitFlash` and M5 guard
   prefabs deliberately NOT switched on — reasons and the Phase 6/7 plan in ADR-016 §5–7; dump evidence `evidence/phase5/m5_dump.txt`.
3. **P5-M7 — report**: `reports/phase5.md` (Appendix F), ADR-016 (ECS-lite + legacy views + replay snapshot v2), CHANGELOG, `ae_ci.py` full run,
   delete `tools/ae_d4_replay_compat.py` once `baseline_v0` is retired.

(History below: the Phase 4 steps that were "next" before Phase 5 opened.)
1. **Phase 4 step 1 DONE 2026-10-15 — `engine.text` landed** (`src/engine/text/`: string tables + `T()` over
   `src/game/content/strings/en.json`, font registry `load_face` — `core.config._load_font` now delegates —,
   `missing_glyphs` + the faces table behind the smoke `font_glyph_coverage` check, layout `measure`/`wrap_lines`/
   `ellipsize`/`check_fit`/`draw_line` with the dev overflow outline). The fontTools TTF read lives in
   `src/core/font_coverage.py` — engine code imports stdlib + pygame only (boundary rule E1). Evidence:
   `tests/unit/test_engine_text.py` (12 tests), API snapshot re-recorded 32→**36 modules / 181→221 names**,
   golden 373/373, replay 5/5, loop 7/7, smoke OK. Star narrowing also done (51/51 sites, B-019,
   `evidence/a001_star_narrowing_20261015/`).
2. Phase 4 (in progress): `engine.ui` kernel landed — `Theme` (`src/engine/ui/theme.py`) + `engine.ui.std` with
   **ObjectiveBanner**, **MiniMap**, **HealthBar**, **WeaponPanel (MagIcons)** and **Hostiles**; `src/ui/hud.py` keeps
   the legacy names as A-009 shims over one theme built from `core.config` (MiniMap moved mechanically, rewrite diff in
   `build/ae_reconcile/minimap_move_diff.txt`). **M5 + M4 HUDs migrated** onto the widgets (census: m4 100→**0**
   draw/blit sites, m5 114→**5**; golden 373/373 + loop m4/m5 600 frames each; m4 bake pack re-baked 58/58
   byte-identical). Unit coverage `tests/unit/test_engine_ui.py`; API snapshot re-recorded **44 modules / 239 names**
   (B-020 fixed the comparator's key-order sensitivity). The first full CI after the move caught 11 boundary
   violations of my own making (fontTools inside `engine.text`, 3/4-level `engine.ui.std.<widget>` imports) — B-021:
   fontTools moved to `core.font_coverage`, every call site imports the 2-level facade
   (`from engine.ui import health_bar`), `BOUNDARIES: OK`. Remaining: M3 → M2 → M1 per-mission HUD bodies, then the
   rest of the `ui/hud.py` widgets (crosshairs/reticle, desk note, notebook, keypad — they need the STATE/audio
   context injected).
3. Phase 4 step 3 DONE 2026-10-15 — **DialogueBox, M1/M2 HP + hostiles, string tables + fit gate.** `engine.ui.std.dialogue_box`
   (131 lines moved verbatim from `cutscenes/engine.py`; `draw_dialogue_box` / `reset_dialogue_slide` are A-009 shims, the
   slide state lives in the widget and the cutscenes facade live view reads it — locked by `tests/unit/test_engine_shims.py`).
   `health_bar.draw` gained geometry arguments so M1's compact strip (full-width bar, label above, plain backdrop via a
   mission-side `panel_bg`) and M2's `unified_w` panel (296 with the OS-12) are the same widget; `hostiles` + `health_bar` +
   `objective_banner` + `weapon_panel` + `dialogue_box` draw their text from `game/content/strings/en.json` (7 keys) through
   `T()`. New **`tools/ae_text_check.py`** (CI row 6: table hygiene, key coverage, placeholder match, 7 fit slots at the
   shipped font sizes) and migration inventory `docs/engine/audit/text_migration.md` — 501 player-facing literals are still
   rendered directly, that is the measured size of the remaining string work. Then `engine.ui.std.bottle_hud` (M1 + M2's
   identical 246x36 molotov strip; M2 imported M1's icon painter) and `engine.ui.std.crosshair` (the combat reticle
   inlined byte-identically in M1/M2/walking_sim + `ui.hud.draw_combat_reticle`, and the colour-blind palette chain in
   five places): shape + palette are engine-owned, the gating policies stay game-side. Census: m1 47/47 → 37 draw/40 blit,
   m2 38/28 → 32/21, m3 1/4, m4 0/0, m5 3/2, ui 40/34 → 32/34. Gates: golden 373/373, loop 7/7 (both re-run after B-022),
   units 173, smoke OK, m1+m2 bake packs re-baked 31/31 byte-identical, full CI 13/13 (`build/ae_reconcile/ae_ci_crosshair.log`).
   Then increment 4: the plate chrome is shared (`entities/art_cache.get_plate_bg`, locked to the legacy pixels by
   `tests/unit/test_art_cache.py`) and the first **mission-side** strings landed (11 HUD labels - hold clock, convoy/raid
   plate, clock + HEAT, visibility chip; `T` is `TILE_SIZE` in m4/m5/quarter, so those modules import it as `_T`). Table is
   20 keys / 20 fit slots, inventory now 21 calls / 498 direct literals. Findings this pass: **B-023** (the
   `_safe_convert_alpha` guard checked `display.get_init()` but not a live surface) fixed; **B-024** open - the m5 bake pack
   is stale for 3 artifacts (`inspect_art_0/5`, `tram_wreck_0`), the staleness gate cannot see it (missing pack deps), and
   regenerating moves the golden `gp.m5.quarter_mid`, so it is a visual + re-baseline decision (fresh copies kept in
   `build/ae_reconcile/baked_m5_fresh/`). Units 175, full CI 13/13 (`build/ae_reconcile/ae_ci_plate.log`).
4. **Phase 4 exit DONE 2026-10-15 — the full Work list is ground out** (`reports/phase4.md`, subsystem docs
   `subsystems/ui.md` + `subsystems/text.md`, evidence `phase4_ui_20261015/`). `_draw_prompt_tag` (M3) and
   `m5/decor.draw_prompt` collapsed into **`engine.ui.std.prompt`** (M3's body is the default; M5 passes its
   chrome, `clamp=False`, and `[E] look` / `[E] look again` now read the table); NameTag (arena
   `_draw_name_tag`) and StealthIndicator (M5 visibility chip) are single-copy UI so no extraction —
   documented instead; Menu/Toast are not on the master Work list. Then the **string migration finished**:
   one-shot codemod `build/ae_reconcile/migrate_strings.py` moved **480 `X.render(<literal>)` sites** into the
   table (plain literals + simple f-strings) and 16 f-strings were hand-migrated (`_T("key", name=...)` with
   `{name}` entries; the dev-console echo stays a literal on purpose, and the 2 sites inside the frozen m5
   inspect-art closure were reverted — see B-024). Table **488 keys / 518 call sites /
   21 fit slots**; inventory: **3 direct literals left** (console + those 2). Gate trail: units 176, API
   **48 modules / 258 names** (prompt recorded), golden **373/373**, loop **7/7**, m1–m4 bake packs re-baked
   **byte-identical** (only `.bakeinfo.json`), text gate `0 missing, 0 unused`, full CI 13/13
   (`build/ae_reconcile/ae_ci_phase4d.log`; an earlier run of the same tree showed 2 false-red rows while another gate
   run and a game process shared the machine — B-027). **No golden was re-baselined in Phase 4.** Codemod traps
   recorded as **B-025** (AST column offsets are UTF-8 byte offsets; any binding of `T` — e.g.
   `from core.config import TILE_SIZE as T` in `tram_wreck.py` — must force the `_T` alias) and **B-026**
   (`"{02}"` is a positional index, not zero padding — six hand-migrated format strings fixed, src scan
   added; the smoke test's settings draw caught it).
5. Phase 5 + the carried tail: `engine.world` / standard systems; **B-024 is an owner decision** (regenerate
   the m5 art + re-baseline `gp.m5.quarter_mid` + add the pack deps, or confirm the committed art); the
   remaining `ui/hud.py` widgets (desk note, notebook, keypad — they need STATE/audio context injected) with
   the PAUSED / NOTEBOOK_INSPECT scene lift (ADR-014) and the boot refactor (B-007/A-001); B-014/B-015
   art-owner triage stays open (advisory) so `--lint --strict` can become the CI mode.
