# RPE6 Phase 0 audit

Status: first pass, 2026-10-11. Static facts are produced by `python tools/ae_audit.py` (stdlib only, read-only) and land in `docs/engine/audit/`. This page summarises them and corrects master-prompt §3. Re-run the tool after any structural change. Do not hand-edit the generated files.

**Caveat first:** every count here is a *static* AST count. Loops multiply real per-frame draw calls; lazy imports and `getattr` indirection can hide edges. The duplication detector only finds functions of 6+ statements that are identical after renaming. It did **not** detect the M4 → M5 HUD copy reported in §3.2, so treat that copy as unconfirmed by tooling and audit it by hand in Phase 4.

## 1. Environment (verified)

| Item | Observed | Evidence |
|---|---|---|
| Repo root | `E:\Code\Call of Acaristan\First try` (spaces) | workspace root |
| Python | 3.13.3 | `python --version` |
| pygame-ce | 2.5.5 (SDL 2.32.6) | `pygame.version.ver` |
| numpy | 2.2.6 | `numpy.__version__` |
| moderngl | imported by `engine3d` (GL backend) | `audit/imports.md` external imports |
| Reference machine | i7-12700KF, 32 GB, Radeon RX 7800 XT, Windows 11 Pro | WMI |
| Git | branch `main`, HEAD `310c385`. **The working tree is dirty**: 246 deleted, 18 modified and 59 untracked paths, from the owner's in-progress cleanup (PDFs/, TXTs/, `__pycache__`, `_cb_shots/`, ...) | `git status --short` |
| Smoke test | `SMOKE TEST: OK`, 131 named checks OK (before any RPE6 change) | `%TEMP%\ae\smoke_before.out` |

## 2. Source layout (corrects §3.2)

src: **167 files / 119,819 lines**. tools: **98 files / 35,565 lines**. Full table: `audit/inventory.md`.

| Package | Files | Notes |
|---|---:|---|
| `missions/` | 50 (61,103 lines) | m1 6, m2 9, m3 15, m4 8, m5 43 files, plus `arena.py`, `walking_sim.py`, `walking_attack3d.py` |
| `ui/` | 13 (18,516) | `match_screen.py` 3,741, `mp.py` 3,408, `upload_os.py` 3,096 |
| `cutscenes/` | 21 (13,181) | dispatcher `engine.py` plus per-mission take modules (`m3ops`, `m3cell`, `m3ko`, `m3broadcast`, `m3ending`, `m4aftermath`, `m5martial*`, `m5mid3d`, ...) |
| `core/` | 28 (6,967) | `config.py`, `state.py` (`STATE = GameState()` at line 405), `game_core.py`, **`fixedstep.py` (a fixed-step clock already exists and is used only by multiplayer)**, `mapbuilder.py`, `artpack.py`, `lighting.py`, `render_util.py`, `level_editor.py`, `console.py` |
| `entities/` | 11 (4,975) | `enemy_ai.py`, `player.py`, `sprite_lib.py`, `death_anim.py` |
| `audio/` | 4 (4,176) | `audio.py` 3,197 lines |
| `net/` | 8 (3,355) | multiplayer, not mentioned in §3 |
| `engine3d/` | 4 (1,932) | software + GL backends, rig |
| `art/` | 23 (1,044) | `art/m5` prototype pipeline (as described) |
| `src/tools/` | 2 (762) | dev code *inside* `src` (`trailer_bot`, `ko_playability_audit`), imported by `app.py` |

**Corrections to §3:**
- "A very large shared draw module (≈6,600+ lines) with drop-shadow and viewport-hand caches": the largest modules are **mission** draw modules: `missions/m2/draw.py` (7,961 lines) and `missions/m3/draw.py` (7,900). `_DROP_SHADOW_CACHE` lives at `missions/m2/draw.py:6708` and `_VP_HAND_CACHE` at `missions/m3/draw.py:4039`. Whether other missions import them is listed in `audit/imports.md`.
- A fixed-step clock (`core/fixedstep.py`) and an FSM game-state manager (`gsm` in `app.py`, with `enter/handle_event/update/render` states) already exist. Phase 1 and Phase 2 should wrap them, not replace them (ADR-001 note).
- An older golden harness exists: `tools/golden.py` (3 M3 stills, 40×28 grayscale signature) is called from the smoke test. `tools/ae_golden.py` supersedes it as the parity oracle but does not remove it.
- 3 files have **mixed** line endings (`src/cutscenes/m5martial.py`, `src/missions/m5/draw.py`, `tools/smoke_test.py`) and 28 are pure CRLF (all under `tools/`). The rest (234) are LF.
- All files decode as UTF-8, with no BOMs. **210 mojibake lines** (double-encoded `─`/`═` banners), worst in `missions/m2/draw.py` (111) and `app.py` (28). See `audit/hazards.md#mojibake`.

## 3. Import graph and boundary (D1 baseline)

`audit/imports.md` has the package edge table and every edge.

- **169 shared → mission edges (141 top-level, 28 lazy).** These are the boundary violations to remove.
- By source file: `cutscenes/__init__.py` 66 (facade re-exports every per-mission take), `cutscenes/engine.py` 57 (the dispatcher imports take modules by name), `core/console.py` 18, `cutscenes/chair.py` 8, `src/tools/ko_playability_audit.py` 8, `core/game_core.py` 7 (mission routing), and one each in `entities/death_anim.py`, `ui/arena_view.py`, `ui/match_screen.py`, `ui/multiplayer_style.py`, `ui/system.py`.
- By target: `cutscenes.m3ops` 37, `cutscenes.m3cell` 26, `missions.m3` 23, `cutscenes.m3ko` 19, `cutscenes.m3broadcast` 15, `missions.m2` 14, `cutscenes.m3ending` 9, `cutscenes.m4aftermath` 8, `cutscenes.m5martial` 8.
- Implication: the cutscene dispatcher is the single biggest boundary problem. A name → take registry (Phase 2/8) removes about 120 of the 169 edges.

## 4. Global-state census (D3/D4 baseline)

`audit/state_census.md` lists every reference with file:line.

- **6,348 `STATE.<field>` references (2,428 writes) to 478 distinct fields.** 275 of those fields are mission-named (`missionN_*` / `mN_*`).
- References by owner: m3 1,987 · m2 1,292 · m1 654 · tools 597 · m5 519 · m4 421 · entities 280 · core 212 · walking_sim 136 · app 119 · ui 111 · fx 20.
- Most-touched fields: `player` 919, `enemies` 221, `floating_texts` 126, `player_dead` 112, `mission3_stage` 103, `doors` 76, `current_weapon` 72, `mission2_stage` 67, `mission_phase` 65, `particles` 65.
- **Shared code touching mission-named fields:** tools 251, app 35, core 24, entities 9, ui 3. Each is a D3 violation (`STATE.missionN_stage` branching in shared code).

## 5. Duplication census

`audit/duplication.md` (normalised-AST hashing).

- 10 exact groups (≈121 redundant statements) and 6 structural-only groups.
- Real copy-paste across missions: `_radio` (m3/m4/m5 `world.py`), `_update_shooting` (m4/m5 `systems.py`), `_arm_loyalist_hunt`/`_arm_hunt` (m4/m5), `_snap_camera_to` (m2/m3), `_outline_building` (m2/m3), `_m3/_m4_ground_ao` and `_ground_blob` (m3/m4 draw), `_update_camera` and `_solid_walls` (m4/m5), `_play_typewriter_tick` (app + m3 interrog + walking_sim).
- The facade `__getattr__` (7 copies) is intentional per AGENTS.md. It gets a shared helper in Phase 1.
- **Not detected:** the M4 → M5 HUD copy. Most HUD functions were edited after copying, so their structure differs. A token-level (winnowing) detector is a follow-up if Phase 4 needs it.

## 6. Draw census

`audit/draw_census.md`. This is a static count. `tools/m5_draw_audit.py` remains the runtime counter for M5.

- 903 functions with draw/blit/fill call sites, **9,245 call sites**. By owner: m3 2,877 · m2 1,297 · m5 1,211 · ui 1,081 · cutscenes 771 · m4 562 · walking_sim 441 · m1 317 · entities 247 · core 231.
- Top functions: `_draw_archives_wing_details` (m3/draw.py:2861, 228), `_game_draw_inner` (m1/draw.py:821, 144), `_draw_cell_details` (m3/draw.py:6300, 107), `draw_server_browser` (ui/mp.py:2552, 93), `_draw_garden` (m2/draw.py:3280, 92). These are prime static-layer bake candidates for Phase 6.
- 1,113 mission-code `pygame.draw.*(screen, ...)` calls draw directly on the screen surface (D6 baseline).

## 7. Cache census

`audit/cache_census.md`. Of 16 module-level caches and memoised functions, **13 have no invalidation path**:

`art/m5/__init__._CACHE`, `core/render_util._RADIAL_ADD_CACHE`, `cutscenes/m4aftermath._arrest_room()` and `_film_shade()` (lru_cache), `cutscenes/m5fx3d._CACHE`, `cutscenes/m5martial3d._cache`, `entities/sprite_lib._CACHE`, `missions/m2/draw._DROP_SHADOW_CACHE`, `missions/m3/draw._VP_HAND_CACHE`, `missions/m5/draw._GUARD_ROT` and `_MAG_SPRITES`, `missions/m5/inspect_art._cache`, `missions/m5/inspect_fpv._static`.

Three have one: `core/artpack._CACHE`, `core/lighting._TINT_CACHE`, `entities/enemy_ai._walk_grid_cache`. Key shapes still need a per-site read when each cache migrates into `engine.assets` (Phase 3). The detector matches cache-like names only, so caches with other names are missed.

## 8. Hazards (rules that legacy code violates today)

`audit/hazards.md` has every site.

| Rule | Count | Where |
|---|---:|---|
| R7 import-time side effects (`set_mode`, `init`, `image.load`, `Surface` at module level) | 52 | `core/config.py` 15 (`pygame.init` :14, `set_mode` :32, `image.load` :154), `ui/system.py` 14, `ui/widgets.py` 8, `app.py` 6, `fx/effects.py` 3 |
| R6 global `random.*` calls | 495 | missions 306, entities 78, ui 49, core 30, audio 21 |
| R6 wall-clock reads (`time.time`, `get_ticks`, `perf_counter`) | 232 → **26** (M3, 2026-10-14) | was: missions 105, app 57, ui 40, net 12, entities 8. Now: net 12 (`monotonic`/`time.time`, real time by design), save timestamps 2, engine boot/fallback 2, profiling 2, smoke harness 1, `ui/match_screen.py` 1 `monotonic`; game code reads `engine.core.now_ms/now_s` (`audit/hazards.md#wall_clock`) |
| D5 direct `pygame.image.load` | 7 | core 2, missions 2, art 1, entities 1, ui 1 |
| D5 direct `mixer.Sound`/`music.load` | 10 | audio 9, ui 1 |
| Banned #2 `getattr(x, "_private", default)` | 32 | see file |
| R14 mojibake lines | 210 | see §2 |

## 9. Baselines captured in Phase 0

| Baseline | Command | Result | Evidence |
|---|---|---|---|
| Golden images `baseline_v0` | `python tools/ae_golden.py capture` | 365 shots: 351 cutscene frames (117 shots across 21 lists × t = 25/50/75 %) + 14 gameplay; 0 errors; 33.5 s; 28.5 MB | `tests/golden/baseline_v0/manifest.json` |
| Golden reproducibility | `python tools/ae_golden.py verify` | `verified 365 shots: 0 failures` (byte-identical sha256) | `%TEMP%\ae\g_verify.out` |
| Replay `baseline_v0` | `python tools/ae_replay.py record` then `check` (separate processes) | m1–m5: 30/30 snapshots match each | `tests/replay/baseline_v0/*.json` |

Determinism findings from building these: see BUGS.md B-001 (gameplay draw reads the wall clock) and B-002 (sim relies on the global `random` stream).
