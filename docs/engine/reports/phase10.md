# Phase 10 report — tooling, docs, Mission 0, final gate (RPE6)

Status: **DONE in the sandbox** (2026-10-16). Debug tools, data-only
editors, the mission scaffolder + tutorial, Mission 0 (D2), validation /
bench-budget / engine3d-parity / packaging tools, full subsystem docs,
a clean human-style gauntlet, and the §13 final gate: `AE CI: OK
(implemented gates)` with **zero TODO rows remaining** (evidence:
`docs/engine/evidence/phase10/final_gate.txt`). Owner reference-machine
re-runs remain pending where noted, as with every phase.

## What changed
- **M1 debug tools** (`src/game/devtools.py`, game-side per ADR-021):
  F3 overlay (frame graph, RenderStats, entity count, scene stack),
  F4 collision view, click inspector with plain-field edit, prefab
  spawn; `~` console (`src/core/console.py`, `Console.bind` command
  set incl. scene/timeline/seed/events/set/spawn/golden/bench).
  Inert unless opened — harnesses never open them, parity untouched.
- **M2 editors**: F5 level viewer and F6 timeline panel (scrub, key
  list, nudge, marks, save) writing data files only through
  `game.timelines.save_timeline()` (canonical indent=1, cache-popped);
  console `tl_*` commands share the writer.
- **M3 Mission 0**: `tools/ae_new_mission.py` scaffolder +
  `docs/engine/tutorial_add_mission.md`; Mission 0 ("Depot") built by
  following them: level/dialogue/timeline/set3d data, thin host over
  `Enemy`/`Player` + `DialogueRunner` + registered cutscene renderers
  (inspect shot + 3D depot shot), `engine.ui` HUD plate, two enemy
  types from `enemy_types.json`, `--dev-mission0` jump, outro consumed
  by `app.py` via `start_cutscene(..., "MISSION_COMPLETE")`.
  `tools/ae_mission0_check.py`: engine-tree sha256 (82 files,
  `e26ff0bd…baf`, frozen pre-M0) unchanged + scripted headless
  playthrough (briefing → BFS walk → exit → outro) + all outro shots
  rendered non-blank.
- **M4 tools**: `tools/ae_validate.py` (49 content files via public
  loaders); bench budgets (`tools/bench_budgets.json` +
  `ae_bench.py --check-budget`); `tools/ae_engine3d_parity.py`
  (software determinism; GL diff = owner run); `tools/ae_package.py`
  (RPE6-0.1.0.zip, 1076 files, 34.8 MB, hashed manifest; `dist/` built
  on demand, deleted after evidence).
- **M5 docs + gauntlet**: `docs/engine/ARCHITECTURE.md`, subsystem
  pages for all 16 kernel packages (14 new + ui/text), STATUS path
  correction. `tools/ae_gauntlet.py`: **clean** — 92 timeline shots at
  two fresh offsets (137 ms / duration−271 ms) + 5 gameplay segments ×
  30 shifted-input frames, no S1/S2 (`evidence/phase10/gauntlet.txt`).
- **M6**: ADR-021; W1 baseline 48 → 49 (the one deliberate
  `core.game_core -> missions.m0` edge; ADR-021 §3 — the accidental
  same-phase W1 edges were fixed through app bindings instead);
  full CI green (below).

## D1–D12 evidence table

| # | Verdict | Evidence |
|---|---|---|
| D1 Boundary | PASS | CI "boundary lint" OK: 0 engine violations, 82 modules; W1 49 (= baseline, ADR-021) |
| D2 Mission 0, zero engine edits | PASS | CI "mission 0 zero-engine-diff" OK: tree sha `e26ff0bd…` == pre-M0 freeze; headless playthrough completes; tutorial was followed literally (`docs/engine/tutorial_add_mission.md`) |
| D3 Scenes, not flags | PASS (Phase 2 state, held) | boundary + scene-mirror audits in CI; no regressions (golden/loop/replay OK) |
| D4 Entities, not attributes | PASS | CI "entity components (D4 grep gate)" OK: hard=0, ratchet 0; "component dump" row OK (one P10-era false-positive pattern in devtools fixed, not exempted) |
| D5 One asset pipeline | PASS (held) | CI "asset bake check + lint" OK: stale=0 missing=0 mismatched=0 |
| D6 One 2D render path | PASS (held) | CI "render queue" OK: custom draws m1–m4=1 each, m5=0; golden 373/373 |
| D7 Data-driven content | PASS | CI rows level/dialogue/timeline/set3d data OK + new "data validation" row (49 files); ADAPTERS.md current (A-001…A-013) |
| D8 Determinism | PASS | CI "replay determinism" 5/5 + "save snapshots reproduce replay" OK |
| D9 Tooling | PASS | F3/F4/F5/F6 + `~` console + click inspector in `src/game/devtools.py`; `tests/unit/test_devtools.py` 5 OK; timeline/level editors write data only (M2 gate; checklist below) |
| D10 Quality gates, one command | PASS | `python tools/ae_ci.py` → `AE CI: OK (implemented gates)`, 26 rows, 0 TODO (`evidence/phase10/final_gate.txt`) |
| D11 Documentation | PASS | ARCHITECTURE.md + 16 subsystem pages + tutorial + ADR-001…021 (ADR-021 this phase) |
| D12 Performance | SANDBOX-INDICATIVE | CI "frame budget bench" OK vs recorded sandbox caps (avg 11.92 ms, p99 16.88 vs caps 17/24); the §6.22 10 ms certification is the owner-machine re-run (`ACA_BENCH_SET` unset), as pre-agreed in the Phase 10 plan |

D9 demo checklist (run `python acaristan.py --dev` or any mission):
F3 overlay · F4 collision · click an entity (inspector) · `~` then
`scene` / `seed 42` / `tl_list` · F5 level viewer · F6 with a cutscene
loaded: scrub, `tl_nudge`, save — the file rewrites canonically and
the game keeps running.

## Incidents / honesty
- **B-038 (open, owner action)**: the Phase 10 opening recapture ran
  without `ACA_GOLDEN_SET=sandbox_linux` and overwrote the owner's
  `tests/golden/baseline_v0` (373 PNGs) with sandbox renders of
  unchanged code. Originals survive only on the owner machine; the
  owner re-export restores them. All sandbox gates used
  `sandbox_linux` sets and are unaffected. Logged in BUGS.md +
  CHANGELOG at the time it happened.
- Sandbox exit state, per precedent: GL engine3d diff, the 10 ms
  bench certification, and the owner `baseline_v0` re-verification
  are owner-machine runs, stated plainly — nothing here claims them.

## Gate (sandbox, 2026-10-16)
`AE CI: OK (implemented gates)` — 26/26 rows OK incl. golden 373/373
(sandbox_linux), loop 7/7, replay 5/5, units 276 OK, smoke OK,
boundaries OK (W1 49 =), API 79 modules / 535 names, gauntlet clean.
First CI run caught one real defect (D4 grep hit in devtools M1
code), fixed in code and re-run green — no re-baselining anywhere
in this phase.
