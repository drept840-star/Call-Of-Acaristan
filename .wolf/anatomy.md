# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-10-21T11:56:34.981Z
> Files: 892 tracked | Anatomy hits: 0 | Misses: 0

> Project structure index. Auto-maintained by OpenWolf hooks and daemon.
> Run `openwolf scan` to generate, or wait for the first Claude Code session.
> Status: Pending initial scan

## ./

- `.gitattributes` — Git attributes (~97 tok)
- `.gitignore` — Git ignore rules (~763 tok)
- `acaristan.py` — Thin launcher — run with `python acaristan.py` from the repo root. (~106 tok)
- `AGENTS.md` — Agent workflow (read this first) (~2517 tok)
- `build.bat` (~56 tok)
- `CLAUDE.md` — OpenWolf (~168 tok)
- `GEMINI.md` — OpenWolf (~75 tok)
- `HANDOFF_CLAUDE.md` — Handoff — Claude (~1583 tok)
- `MEMORY.md` — RULE: Split long tasks into Planning and Writing stages (~554 tok)
- `pyproject.toml` — Python project configuration (~53 tok)
- `README.md` — Project documentation (~286 tok)

## docs/

- `AUDIT_T1_CAPTURE_PIPELINE.md` — AUDIT T1 — Capture Pipeline (Video Recording / Rendering / Frame Capture) (~4418 tok)
- `AUDIT_T2_ASSETS_AND_REPLAYS.md` — AUDIT T2 — Assets & Replays: Is the video pre-recorded or live-rendered? (~3661 tok)
- `AUDIT_T3_ALL_CHECKPOINTS.md` — AUDIT T3 — All Playable Combat Checkpoints (~3477 tok)
- `AUDIT_T4_BOT_INPUTS.md` — AUDIT T4 — Bot Inputs & Autonomous Controller (READ-ONLY) (~4557 tok)
- `AUDIT_T5_STRING_ORIGINS.md` — AUDIT T5 — String & Overlay Origins (~4873 tok)
- `AUDIT_T6_TIMELINE_LOGIC.md` — AUDIT T6 — Timeline & Scene Queue Analyst (~5982 tok)
- `AUDIT_T7_ENEMY_SPAWNS.md` — AUDIT T7 — Enemy Spawning & Combat Density (READ-ONLY) (~7441 tok)
- `AUDIT_T8_STANDALONE_PLAN.md` — T8 — Standalone Capture Architect: `record_fresh_action.py` (~5296 tok)
- `DOCUMENTARY.md` — CALL OF ACARISTAN — A DOCUMENTARY (~3159 tok)
- `FIXES_STORIES.md` — FIXES_STORIES — story consistency pass (~3645 tok)
- `KRAPNET_MULTIPLAYER.md` — KRAPNET — self-hosted multiplayer (host a lobby, share an address) (~7711 tok)
- `LORE.md` — Call of Acaristan — Lore & World Dossier (~4505 tok)
- `M5_FINALE_REBUILD_PLAN.md` — M5 finale — The Shadow (integrated build) (~1768 tok)
- `M5_SHADOW_RECORDING_GUIDE.md` — M5 shadow finale — recording handoff (~515 tok)
- `manifest.json` (~1868 tok)
- `MASTER_ACTION_PLAN.md` — MASTER ACTION PLAN — Video Capture Pipeline (~5000 tok)
- `MISSION3_KILL_ORDER.md` — Mission 3 · Phase 5 — THE KILL ORDER (Slice 5 plan) (~4068 tok)
- `MISSION3_PLOT.md` — Mission 3 — "The Vostral" (~2435 tok)
- `MISSION4_PLOT.md` — Mission 4 — "The Aftermath" (~2620 tok)
- `MISSION5_BUILD_PLAN.md` — Mission 5 "Martial Law" - Build Plan (milestones) (~761 tok)
- `MISSION5_PLOT.md` — Mission 5 — "Martial Law" (~1972 tok)
- `MISSION6_PLOT.md` — Mission 6 — "Black Notebook" (~3462 tok)
- `MISSION7_PLOT.md` — Mission 7 — "Fallow Ground" (~2237 tok)
- `MISSION8_PLOT.md` — Mission 8 — "The Call" (~4123 tok)
- `OIL_RIG_BOMBING_CUTSCENE.md` — The Oil Rig Bombing Cutscene (~364 tok)
- `PLAN_1_CHOREOGRAPHY.md` — PLAN 1 — Bot Gameplay & Tactical Choreography (AI 1, actionable) (~4204 tok)
- `PLAN_2_EDITOR.md` — PLAN_2_EDITOR — Trailer Overhaul EDL (58s Locked) (~1880 tok)
- `PLAN_3_AUDIO.md` — PLAN_3_AUDIO — Official 60s Trailer Overhaul (Audio Director) (~2337 tok)
- `PLAN_4_VISUALS.md` — PLAN_4_VISUALS — Trailer Overhaul (Art Director / Post-Production) (~1856 tok)
- `README_ENV_SETUP.md` (~254 tok)
- `thumbnail_pick.json` (~821 tok)
- `TRAILER3D_PLAN.md` — Call of Acaristan - Cinematic 3D Trailer ("THE CALL") (~1232 tok)
- `worklog.md` — Declares with (~28723 tok)

## docs/engine/

- `ADAPTERS.md` — ADAPTERS (legacy ↔ engine bridges and their removal plan) (~3615 tok)
- `ARCHITECTURE.md` — Retardovici Pulse Engine 6 Gold — Architecture (~1100 tok)
- `AUDIT.md` — RPE6 Phase 0 audit (~2532 tok)
- `BUGS.md` — BUGS (found during RPE6 work; R16: log, fix only if S1 or blocking) (~9167 tok)
- `CHANGELOG.md` — Change log (~8683 tok)
- `ENGINE_MASTER_PROMPT.md` — RETARDOVICI PULSE ENGINE 5 — MASTER PROMPT (~25387 tok)
- `gitattributes.proposed` — RPE6 Phase 0 line-ending policy (master prompt R14). Copy to /.gitattributes in its own commit. (~100 tok)
- `STATUS.md` — Retardovici Pulse Engine 6 Gold: STATUS (~12648 tok)
- `tutorial_add_mission.md` — Tutorial: add a mission (RPE6) (~1842 tok)

## docs/engine/adr/

- `ADR-000-template.md` — ADR-NNN: <title> (~77 tok)
- `ADR-001-package-layout.md` — ADR-001: Package layout — `src/engine/` plus keeping `missions/` (no `game/` move yet) (~483 tok)
- `ADR-002-ecs-lite.md` — ADR-002: ECS-lite — dataclass components in per-type dicts, adapters over legacy objects (~350 tok)
- `ADR-003-data-formats.md` — ADR-003: Data formats — versioned JSON with stdlib validators, optional Tiled import (~364 tok)
- `ADR-004-fixed-timestep.md` — ADR-004: Fixed timestep and the engine clock (~404 tok)
- `ADR-005-frame-coherent-wall-clock.md` — ADR-005: Frame-coherent wall clock and the `grain` rng stream (~1071 tok)
- `ADR-006-golden-tolerances.md` — ADR-006: Golden-image oracle — software backend, pinned clock, tolerances, storage (~438 tok)
- `ADR-014-scene-stack-and-fsm-mirror.md` — ADR-014: Scene stack semantics and the FSM mirror (~952 tok)
- `ADR-015-asset-ids-and-hashing.md` — ADR-015: Asset ids, manifests, bake hashing and the fallback chain (~2954 tok)
- `ADR-016-legacy-world-bridge.md` — ADR-016: The legacy world bridge — view components, mission components, hosted SIM, render-driven WalkCycle (~1755 tok)
- `ADR-017-render-queue-authored-order.md` — ADR-017: One render queue, authored order, submit-time side effects (~1785 tok)
- `ADR-018-level-and-dialogue-data.md` — ADR-018: Levels and dialogue as validated data, generators as fallback (~1157 tok)
- `ADR-019-timeline-and-set3d-data.md` — ADR-019: Cutscene timelines and 3D sets as data, takes as registered hooks (~1297 tok)
- `ADR-020-settings-save-input-kernels.md` — ADR-020: Settings, save snapshots and input as engine kernels; legacy stores as clients (~1196 tok)
- `ADR-021-devtools-editors-mission0.md` — ADR-021: Game-side dev tools, data-only editors, Mission 0, and the W1 49 baseline (~875 tok)
- `ADR-022-3d-visual-upgrades-steps1-4.md` — ADR-022: 3D visual upgrade track, steps 1–4 (Phase 11) (~928 tok)
- `ADR-023-cast-shadows.md` — ADR-023 — Cast shadows: baked per-face raycasts (no shadow maps) (~616 tok)
- `ADR-024-mesh-import.md` — ADR-024 — Mesh import: glTF/GLB + OBJ → ae.mesh/1 through the asset pipeline (~530 tok)

## docs/engine/audit/

- `cache_census.md` — Cache census (module-level cache containers and memoised functions) (~740 tok)
- `draw_census.md` — Procedural draw census (RPE6 Phase 3, P3-M3) (~1923 tok)
- `duplication.md` — Duplication census (normalised-AST hashing) (~789 tok)
- `hazards.md` — Hazards (rule violations to retire in later phases) (~6715 tok)
- `hud_duplication.md` — HUD duplication census (Phase 4 prep) (~744 tok)
- `imports.md` — Import graph (~4238 tok)
- `inventory.md` — Inventory (~8101 tok)
- `star_imports.md` — `from core.config import *` inventory (A-001 prep) (~242 tok)
- `state_census.md` — Global-state census (`STATE.<field>`) (~100570 tok)
- `text_migration.md` — Text migration inventory (Phase 4) (~670 tok)

## docs/engine/evidence/

- `overlay_manifest.txt` (~9097 tok)

## docs/engine/evidence/a001_star_narrowing_20261015/

- `README.md` — Project documentation (~658 tok)

## docs/engine/evidence/phase10/

- `final_gate.txt` (~917 tok)
- `gauntlet.txt` (~21 tok)

## docs/engine/evidence/phase11/

- `final_gate_steps5-11.txt` (~953 tok)
- `final_gate.txt` (~954 tok)
- `gauntlet_steps5-11.txt` (~451 tok)
- `gauntlet.txt` (~21 tok)

## docs/engine/evidence/phase4_ui_20261015/

- `README.md` — Project documentation (~4411 tok)

## docs/engine/evidence/phase5/

- `d4_baseline.json` (~15 tok)
- `m3_bridge_gate.txt` (~57 tok)
- `m4_gate.txt` — P5-M4 gate (2026-10-15T19:36Z), Linux sandbox, ACA_GOLDEN_SET=ACA_LOOP_SET=sandbox_linux, PYTHONHASHSEED=0 (~302 tok)
- `m4_replay_compat.txt` — P5-M4 replay compatibility proof (2026-10-15) - baseline_v0 (snapshot v1) vs current code (~191 tok)
- `m5_dump.txt` — tools/ae_dump_components.py --seg m5 --seconds 3 — Phase 5 exit evidence (running M5 Lower Quarter stage; sandbox 2026-10-15, after P5-M6) (~398 tok)
- `m5_gate.txt` — P5-M5 gate (2026-10-15T20:00Z), Linux sandbox, ACA_GOLDEN_SET=ACA_LOOP_SET=sandbox_linux (recaptured at this point; vs owner baseline_v0 the same 8... (~210 tok)
- `m5_replay_compat.txt` — P5-M5 replay compatibility proof (2026-10-15) - owner's baseline_v0 (snapshot v1) vs current code (M2Role/M3Guard/M4Guard/M5Guard + Label) (~203 tok)
- `m5b_gate.txt` — P5-M5b full gate (sandbox, pygame-ce 2.5.8, SDL dummy, PYTHONHASHSEED=0, golden/loop sets sandbox_linux) — 2026-10-15 (~197 tok)
- `m5b_replay_compat.txt` — P5-M5b (doors) replay compatibility proof (2026-10-15) - owner's baseline_v0 vs current code (M3Door on core.interactions.Door; roster registers ST... (~208 tok)
- `m6_gate.txt` — P5-M6 full gate (sandbox, pygame-ce 2.5.8, SDL dummy, PYTHONHASHSEED=0, golden/loop sets sandbox_linux; compat vs baseline_v1 then owner baseline_v... (~171 tok)

## docs/engine/evidence/phase6/

- `d6_baseline.json` (~165 tok)
- `final_gate.txt` (~357 tok)
- `m3_m5_gate.txt` (~299 tok)

## docs/engine/evidence/phase7/

- `final_gate.txt` (~627 tok)

## docs/engine/evidence/phase8/

- `final_gate.txt` (~661 tok)

## docs/engine/evidence/phase9/

- `final_gate.txt` (~619 tok)

## docs/engine/evidence/reconcile_20261015/

- `compare_manifests.py` — Compare golden manifests: sandbox(A) vs partial `--only` recapture(B) vs full re-baseline(C). (~502 tok)
- `manifest_drift_report.txt` (~330 tok)
- `probe_out.txt` (~681 tok)
- `README.md` — Project documentation (~837 tok)
- `rebaseline_out.txt` (~590 tok)

## docs/engine/evidence/reconcile_20261018/

- `after_ae_ci_run2.txt` (~956 tok)
- `after_ae_ci.txt` (~955 tok)
- `after_bench.txt` (~182 tok)
- `after_bench3d.txt` (~358 tok)
- `after_golden_capture.txt` (~228 tok)
- `after_golden_venv.txt` (~448 tok)
- `after_golden.txt` (~128 tok)
- `after_loop_venv.txt` (~59 tok)
- `after_loop.txt` (~59 tok)
- `after_replay_venv.txt` (~505 tok)
- `after_replay.txt` (~416 tok)
- `after_unit.txt` (~1302 tok)
- `before_ae_ci.txt` (~989 tok)
- `before_bench.txt` — `frame budget bench` row of the old CI run (2026-10-18 20:45, wall 396 s). (~115 tok)
- `before_bench3d.txt` — `3d frame budget` row of the old CI run (2026-10-18 20:45, wall 396 s). (~96 tok)
- `before_golden.txt` (~1449 tok)
- `before_loop.txt` (~184 tok)
- `before_replay.txt` (~477 tok)
- `before_smoke.txt` (~2526 tok)
- `before_unit.txt` (~1650 tok)
- `README.md` — Project documentation (~1603 tok)

## docs/engine/evidence/tierB/

- `census.txt` (~339 tok)
- `ci_tierB.txt` (~347 tok)
- `m124_sprite_parity.txt` (~241 tok)
- `m3_sprite_parity.txt` (~104 tok)

## docs/engine/reports/

- `phase0_normalisation.txt` — ae_normalize APPLY (~1233 tok)
- `phase0.md` — Phase 0 report — Audit, baseline, hygiene (~1187 tok)
- `phase1.md` — Phase 1 report — Kernel: App, Clock, Services, no import side effects (~1264 tok)
- `phase10.md` — Phase 10 report — tooling, docs, Mission 0, final gate (RPE6) (~1644 tok)
- `phase11.md` — Phase 11 report — 3D visual upgrades, steps 1–4 (RPE6) (~2384 tok)
- `phase2.md` — Phase 2 report — Boundary and scene stack (~1223 tok)
- `phase3.md` — Phase 3 report — Asset pipeline (game-wide) (~2163 tok)
- `phase4.md` — Phase 4 report — UI toolkit and text (~2182 tok)
- `phase5.md` — Phase 5 report — World/ECS-lite and standard systems (~2080 tok)
- `phase6.md` — Phase 6 report — Render2D queue, camera, static layers, lighting, post-FX (~967 tok)
- `phase7.md` — Phase 7 report — data-driven levels and dialogue (RPE6) (~735 tok)
- `phase8.md` — Phase 8 report — declarative 3D sets and cutscene timelines (RPE6) (~956 tok)
- `phase9.md` — Phase 9 report — save/load, determinism, settings, accessibility (RPE6) (~672 tok)

## docs/engine/subsystems/

- `anim.md` — Subsystem: `engine.anim` (Phase 4–5) (~196 tok)
- `assets.md` — Subsystem: `engine.assets` (Phases 3, 6) (~276 tok)
- `core.md` — Subsystem: `engine.core` (Phases 1–2, 9) (~358 tok)
- `dialogue.md` — Subsystem: `engine.dialogue` (Phase 7) (~238 tok)
- `input.md` — Subsystem: `engine.input` (Phase 9, ADR-020) (~212 tok)
- `level.md` — Subsystem: `engine.level` (Phase 7) (~203 tok)
- `lighting.md` — Subsystem: `engine.lighting` (Phase 3) (~184 tok)
- `render2d.md` — Subsystem: `engine.render2d` (Phases 2–3) (~302 tok)
- `render3d.md` — Subsystem: `engine.render3d` + `engine3d` (Phases 6, 8) (~614 tok)
- `save.md` — Subsystem: `engine.save` (Phase 9, ADR-020) (~263 tok)
- `scene.md` — Subsystem: `engine.scene` (Phase 2) (~215 tok)
- `settings.md` — Subsystem: `engine.settings` (Phase 9, ADR-020) (~241 tok)
- `text.md` — Subsystem: `engine.text` (Phase 4) (~1122 tok)
- `timeline.md` — Subsystem: `engine.timeline` (Phase 8) (~249 tok)
- `ui.md` — Subsystem: `engine.ui` (Phase 4) (~1244 tok)
- `world.md` — Subsystem: `engine.world` (Phase 3) (~262 tok)

## docs/history/

- `FIXES.md` — Mission 4 fix pass — "The Aftermath" (~1348 tok)
- `IMPLEMENTED.md` — Graphics rework — IMPLEMENTED (all five phases) (~2900 tok)
- `manifest.json` (~1219 tok)
- `MASTER_PROMPT.md` — MASTER PROMPT — Call of Acaristan: The Big Polish & Fix Pass (~12165 tok)
- `MISSION5_W1_README.txt` (~125 tok)
- `MISSION5_W2_README.txt` (~157 tok)
- `MISSION5_W3_README.txt` (~244 tok)
- `MISSION5_W4_README.txt` (~712 tok)
- `MISSION5_W5_README.txt` (~721 tok)
- `MISSION5_W6_README.txt` (~181 tok)
- `MISSION5_W7_README.txt` (~126 tok)
- `MULTIPLAYER_PATCH_README.txt` — Declares ASTs (~870 tok)
- `MULTIPLAYER_PATCH_SHA256.json` (~138 tok)
- `PATCH_INSTRUCTIONS.txt` (~381 tok)
- `PATCH_SHA256.txt` (~150 tok)
- `README.md` — Project documentation (~251 tok)
- `SETTINGS_PATCH_README.txt` (~658 tok)
- `TUNNEL_TEST_RESULTS.txt` (~186 tok)

## docs/prompts/

- `M5_FINALE_MASTER_PROMPT.md` — MASTER PROMPT - Rebuild the M5 finale ("m5_shadow_finale") to M2 quality (~3355 tok)

## src/

- `app.py` — _input_recorder: handle_settings_event (~55601 tok)

## src/art/

- `__init__.py` — Hand-authored pixel-art sprites (pygame-only, no game imports). (~20 tok)

## src/art/m5/

- `__init__.py` — Compatibility shim (ADAPTERS A-008): ``art.m5`` -> ``game.art.m5``. (~322 tok)
- `_kit.py` — Shared pixel-art kit for the Mission 5 sprites. (~1407 tok)
- `armband.py` — The black Guard armband pinned to the depot notice board (25 x 8 px, 0.5 x 0.16 m): (~227 tok)
- `bale.py` — Strapped newspaper bundles seen from above (Print Works stacks/pallets). (~562 tok)
- `calendar.py` — Safehouse wall calendar (24 x 32 px, 0.6 x 0.8 m): red 1991 header, month (~258 tok)
- `district_map.py` — Vasile's district map (52 x 36 px, 1.3 x 0.9 m): street grid, the river, (~438 tok)
- `guard_banner.py` — Presidential Guard banner (36 x 57 px, 1.2 x 1.9 m): brass rod, black (~630 tok)
- `guard_plate.py` — Lit red Guard notice plate over the Print Works door (36 x 20 px, 0.9 x 0.5 m). (~142 tok)
- `hq_locker.py` — Guard HQ steel locker (26 x 44 px, top-down gameplay prop). The dead man's (~388 tok)
- `inspect_art.py` — Static layers of the Mission 5 "[E] look" first-person shots (canvas (~336 tok)
- `m5_guard.py` — Presidential Guard trooper, top-down gameplay sprite (96 x 96, figure (~693 tok)
- `mag_icon.py` — HUD magazine-icon shells (weapon panel). The shell art is static per kind (~776 tok)
- `mag.py` — Maru's thrown magazines (gameplay). Variant 0: K-9 stick mag (12 x 29 px), (~388 tok)
- `maru.py` — Maru, top-down gameplay sprite (84 x 84, anchor (42, 48) = feet/centre): (~288 tok)
- `plate.py` — HUD status plate (convoy / raid clock), 340 x 46: dark glass, steel rim (~248 tok)
- `portrait_frame.py` — Official portrait of President Retardovici in a gilt frame (30 x 30 px, 1.0 x 1.0 m). (~505 tok)
- `posters.py` — Wall posters of the Lower Quarter (32 x 44 px, 0.64 x 0.88 m in the 3D sets). (~1599 tok)
- `presidential_crest.py` — State crests (40 x 40 px). (~785 tok)
- `press.py` — Print Works offset press, top-down (154 x 64). The press bed is the (~652 tok)
- `printworks_sign.py` — "MAG PRINT WORKS" enamel sign over the Print Works (96 x 14 px, 8.4 x 1.3 m). (~251 tok)
- `tram_wreck.py` — Burnt-out tram on the quarter junction (static decor). One variant at the (~210 tok)
- `wall_posters.py` — Top-down wall posters for the gameplay maps (the wall is seen as its front band). (~679 tok)

## src/audio/

- `__init__.py` — audio package. (~7 tok)
- `audio.py` (~33059 tok)
- `voice_manifest.py` — Generated from voice_lines.xlsx - (VO ID, speaker, line) for every voiced line. (~6300 tok)
- `voice.py` — Voice-over playback for Call of Acaristan. (~8837 tok)

## src/core/

- `__init__.py` — core package. (~6 tok)
- `ambience.py` — ambience.py - zone-driven world ambience layers. (~1358 tok)
- `appearance.py` — Character appearance: the cosmetic catalog, the appearance value object, (~7120 tok)
- `artpack.py` — core.artpack - deprecated path (RPE6 Phase 2, A-006). (~251 tok)
- `camera.py` — Shared camera and bullet helpers. (~4512 tok)
- `config.py` — URL patterns: 2 routes (~9537 tok)
- `console.py` — Console: toggle, bind, handle_event, execute_command (~4163 tok)
- `cutscene_registry.py` — Cutscene scene renderers registered by scene id (RPE6 D1, boundary rule 4). (~700 tok)
- `dev_jumps.py` — dev_jumps.py - registry of dev jump targets. (~1678 tok)
- `fixedstep.py` — Fixed-timestep accumulator, for making the simulation host-independent. (~4752 tok)
- `font_coverage.py` — Font glyph coverage - the fontTools half of §6.13 (dev/audit only). (~649 tok)
- `fsm.py` — fsm.py - Finite State Machine infrastructure for Acaristan. (~1929 tok)
- `game_core.py` — game_core.py - Proxy facade that delegates to split modules. (~5830 tok)
- `hands.py` — Canonical hand renderers - the reference-anatomy model (dorsal view). (~4371 tok)
- `interactions.py` — Player interactions with the world: doors, safe, NPCs, alarms. (~6462 tok)
- `json_store.py` — Shared atomic JSON persistence helpers for save_data.json / settings.json. (~413 tok)
- `level_editor.py` — LevelEditor: set_map, toggle, handle_event, rebuild_world + 3 more (~2564 tok)
- `lighting.py` — core.lighting - deprecated path (RPE6 Phase 2, A-006). (~180 tok)
- `mapbuilder.py` — Shared tilemap authoring helper (pure python, no pygame). (~1659 tok)
- `mission_meta.py` — Per-mission display metadata (operation name + failure-screen copy). (~1041 tok)
- `outfits.py` — outfits.py - Biribel's Mission 5 kit, as data (one source of truth). (~2055 tok)
- `profile_store.py` — The global profile: Acaribucks wallet, owned cosmetics, equipped loadout. (~2364 tok)
- `props.py` — props.py - shared set-dressing prop painters. (~5054 tok)
- `render_util.py` — core.render_util - deprecated path (RPE6 Phase 2, A-006). (~223 tok)
- `save_system.py` — 3-slot JSON save system for campaign progress. (~2212 tok)
- `scene_mirror.py` — RPE6 ADAPTER A-005: mirror the legacy GameStateManager onto an engine SceneStack. (~856 tok)
- `settings_store.py` — Settings store - persistent JSON-backed user preferences. (~1856 tok)
- `state.py` — Central game state singleton. (~6475 tok)
- `staticlayer.py` — staticlayer.py - chunked bake of the static world (phase 0). (~1035 tok)
- `surfaces.py` — surfaces.py - floor-material zones for footstep timbre selection. (~536 tok)
- `user_settings.py` — Live user settings - shared across all gameplay modules. (~1320 tok)

## src/cutscenes/

- `__init__.py` — Package cutscenes - re-export facade. Parts: cast.py, cast3d.py, route12.py, m3cell.py, chair.py, m3ops.py, m3ko.py, m3broadcast.py, m3ending.py, m... (~730 tok)
- `cast.py` — cast.py - cutscene cast sprites. (~1275 tok)
- `cast3d.py` — cast3d.py - 3D (engine3d.Humanoid) looks derived from the 2D cast sheet. (~1028 tok)
- `chair.py` — Split from cutscenes.py - see cutscenes.py (shim) for the map. (~17099 tok)
- `engine.py` — Split from cutscenes.py - see cutscenes.py (shim) for the map. (~8428 tok)
- `figure_kit.py` — cutscenes.figure_kit - deprecated path (RPE6 Phase 2, A-006): the kit is ``engine.anim``. (~176 tok)
- `k9.py` — K-9 armory pickup: one continuous, deterministic, software-safe take. (~5003 tok)
- `m3broadcast.py` — Mission 3 - Kill Order -> Broadcast transition cinematic (Slice 5 -> 6). (~10591 tok)
- `m3cell_balaceanu_patch.py` — Replace the body of _m3_draw_balaceanu in src/cutscenes/m3cell.py with this. (~152 tok)
- `m3cell.py` — Split from cutscenes.py - see cutscenes.py (shim) for the map. (~13153 tok)
- `m3ending.py` — m3ending.py - Mission 3 finale cutscene (the Vostral read live on air). (~5003 tok)
- `m3ko.py` — Mission 3 - Kill Order transition cinematic (Slice 5 cutscene rehaul, v2). (~8718 tok)
- `m3ops.py` — Split from cutscenes.py - see cutscenes.py (shim) for the map. (~17136 tok)
- `m4aftermath.py` — m4aftermath.py - Mission 4 finale + intro cutscene art (The Aftermath). (~9390 tok)
- `m5decal.py` — Sprite -> wall decal mesh for the M5 3D cutscenes. (~1129 tok)
- `m5ending3d.py` — Authored M5 ending set and distance-driven actor blocking. (~9970 tok)
- `m5fx3d.py` — m5fx3d.py - FX kit for the Mission 5 3D cutscenes (m5martial3d / m5mid3d). (~6489 tok)
- `m5harbour_art.py` — Authored blocky harbour art for M5; canonical people and motion stay intact. (~10961 tok)
- `m5martial.py` — m5martial.py - Mission 5 intro + ending cutscene art (Martial Law). (~10116 tok)
- `m5martial3d.py` — m5martial3d.py - W7: true-3D (engine3d) takes of every Mission 5 cutscene. (~17280 tok)
- `m5mid3d.py` — m5mid3d.py - Mission 5 mid-mission cutscenes (round 2). (~30984 tok)
- `m5shadow3d.py` — The rebuilt M5 finale: one fresh 3D set, actor clock and camera language. (~13104 tok)
- `m5studio.py` — m5studio.py - the state-TV studio shared by the M5 bulletin's 3D take (~2343 tok)
- `m6films.py` — m6films.py - engine3d takes and 2D fallbacks for every Mission 6 film. (~20560 tok)
- `m6world3d.py` — m6world3d.py - engine3d sets and actor kit for the Mission 6 films. (~24296 tok)
- `oil_rig_3d.py` — True-3D Oil Rig Bombing cutscene (engine3d). Timeline-driven; VO gates shots. (~1907 tok)
- `post3d.py` — Cinematic post stack for cutscene shots (RPE6 Phase 11 step 5). (~1722 tok)
- `route12.py` — Split from cutscenes.py - see cutscenes.py (shim) for the map. (~22720 tok)
- `weather3d.py` — Data-driven weather & atmosphere for 3D sets (RPE6 Phase 11 step 6). (~1610 tok)

## src/engine/

- `__init__.py` — Retardovici Pulse Engine 6 Gold (RPE6): the Call of Acaristan engine. (~88 tok)

## src/engine/anim/

- `__init__.py` — engine.anim - animation (RPE6). Phase 2 holds the generic 2D figure kit (``draw_character`` and the (~252 tok)
- `figure_kit.py` — figure_kit.py - one cast renderer in the "Balaceanu Arrest" house style. (~10926 tok)
- `pose_cache.py` — Pose cache: render-once surfaces for parameterised procedural bodies. (~414 tok)

## src/engine/core/

- `__init__.py` — engine.core: kernel services (clock, rng, events, log, config, services, errors, app). (~365 tok)
- `app.py` — App: explicit boot / run / shutdown (§6.1). The only place that touches the display. (~1678 tok)
- `clock.py` — Fixed-step simulation clock (master prompt §6.1, ADR-004). (~1310 tok)
- `config.py` — Layered settings: defaults < JSON file < environment < CLI overrides (§6.1). (~660 tok)
- `errors.py` — Engine exceptions with context, and the crash-report writer (§6.1, §6.23). (~580 tok)
- `events.py` — Typed event bus (§6.3). Events are any objects; subscription is by type. (~680 tok)
- `log.py` — Structured logging with channels, a ring buffer and warn-once (§6.23). (~592 tok)
- `mathx.py` — Small math helpers (lerp/ease/angles/clamp). (~291 tok)
- `profiling.py` — Scoped timers (§6.22). Uses perf_counter: profiling only, never simulation. (~249 tok)
- `rng.py` — Named, seeded random streams (R6, §6.1). (~664 tok)
- `services.py` — Explicit service registry (§6.1): no magic globals, clear errors. (~325 tok)
- `timebase.py` — Game-time accessors for legacy code (RPE6 ADAPTER A-004, BUGS B-001). (~666 tok)

## src/engine/dialogue/

- `__init__.py` — engine.dialogue - data-driven dialogue (RPE6 §6.14, Phase 7). (~440 tok)
- `model.py` — dialogue.model - the .dlg.json model and static validation (RPE6 §6.14). (~1545 tok)
- `runner.py` — dialogue.runner - DialogueRunner: walk a .dlg.json graph, emit lines (RPE6 §6.14). (~1778 tok)

## src/engine/input/

- `__init__.py` — engine.input - action maps over raw device state (RPE6 §6.10, Phase 9). (~139 tok)
- `model.py` — input.model - action maps and pressed-state remapping (RPE6 §6.10, Phase 9). (~1335 tok)

## src/engine/level/

- `__init__.py` — engine.level - data-driven levels (RPE6 §6.16, Phase 7). (~335 tok)
- `model.py` — level.model - the .level.json model, validation and (de)serialisation (RPE6 §6.16). (~1816 tok)
- `tiled.py` — level.tiled - Tiled JSON (.tmj) importer (RPE6 §6.16). (~1177 tok)

## src/engine/lighting/

- `__init__.py` — engine.lighting - 2D light map (RPE6). Phase 2 absorbs core.lighting's half-res LightBuffer; (~125 tok)
- `buffer.py` — lighting.buffer - half-res light buffer: grade, motivated pools, dust (engine side). (~3261 tok)
- `lightmap.py` — lighting.lightmap - multiplicative 2D light map (RPE6 Phase 6, §6.6 lighting integration). (~1200 tok)

## src/engine/render2d/

- `__init__.py` — engine.render2d - one way to put pixels on screen during gameplay (RPE6 §6.6). (~583 tok)
- `camera.py` — render2d.camera - Camera2D: follow, dead-zone, look-ahead, bounds, trauma shake, zoom (RPE6 §6.6). (~2109 tok)
- `drawables.py` — render2d.drawables - the things a RenderQueue draws (RPE6 §6.6, Phase 6). (~5352 tok)
- `pen.py` — render2d.pen - a drawing sink for procedural painters (RPE6 Phase 6, B-033). (~1088 tok)
- `postfx.py` — render2d.postfx - full-screen post effects as cached surfaces + parameters (RPE6 §6.6). (~1681 tok)
- `queue.py` — render2d.queue - the sorted render queue and its layer table (RPE6 §6.6, Phase 6). (~2055 tok)
- `static.py` — render2d.static - StaticLayers: chunked bakes of floor/decor painters (RPE6 §6.6). (~1650 tok)
- `util.py` — render2d.util - shared gameplay-render helpers (engine side). (~1519 tok)

## src/engine/render3d/

- `__init__.py` — engine.render3d - declarative 3D sets (RPE6 §6.7, Phase 8). (~337 tok)
- `presets.py` — render3d.presets - named 3D lighting moods (RPE6 §6.7 step 1, Phase 11). (~1640 tok)
- `scene3d.py` — render3d.scene3d - declarative 3D sets (RPE6 §6.7, Phase 8). (~3704 tok)

## src/engine/save/

- `__init__.py` — engine.save - snapshots and determinism hashing (RPE6 §6.17, Phase 9). (~182 tok)
- `snapshot.py` — save.snapshot - the ae.save/1 snapshot model (RPE6 §6.17, Phase 9). (~796 tok)
- `statehash.py` — save.statehash - stable world hashing for determinism checks (RPE6 §6.17). (~483 tok)

## src/engine/scene/

- `__init__.py` — engine.scene - explicit scene stack (RPE6 §6.2). Facade only; logic lives in the owner modules. (~95 tok)
- `cutscene.py` — CutsceneScene: a linear sequence of timed shots (§6.2, Phase 2 form). (~1362 tok)
- `inspect.py` — InspectScene: a first-person look at an object that freezes gameplay (§6.2). (~583 tok)
- `scene.py` — Scene: one screen of the game with an explicit lifecycle (§6.2). (~747 tok)
- `stack.py` — SceneStack: the explicit replacement for stage flags and mode switches (§6.2). (~2723 tok)

## src/engine/settings/

- `__init__.py` — engine.settings - typed, layered user settings (RPE6 §6.18, Phase 9). (~190 tok)
- `model.py` — settings.model - typed, layered settings (RPE6 §6.18, Phase 9). (~1795 tok)

## src/engine/text/

- `__init__.py` — engine.text - string tables, the font registry and text layout (§6.12/§6.13). (~372 tok)
- `fonts.py` — Font registry and the glyph verdict (§6.13). (~1001 tok)
- `layout.py` — Text layout: measure, wrap, fit, ellipsis (§6.12). (~1275 tok)
- `strings.py` — String tables (§6.13): keys -> English, ``T()`` with fallbacks. (~971 tok)

## src/engine/timeline/

- `__init__.py` — engine.timeline - data-driven cutscene timelines (RPE6 §6.15, Phase 8). (~376 tok)
- `expr.py` — timeline.expr - the tiny safe expression evaluator (RPE6 §6.7/§6.15). (~1118 tok)
- `model.py` — timeline.model - the .timeline.json model and static validation (RPE6 §6.15). (~2000 tok)
- `player.py` — timeline.player - deterministic sampling of a Timeline at any t (RPE6 §6.15). (~1836 tok)

## src/engine/ui/

- `__init__.py` — engine.ui - the widget kernel and the standard widgets (§6.12, Phase 4). (~312 tok)
- `theme.py` — Theme: the fonts, colours and viewport metrics widgets draw with (§6.12). (~672 tok)

## src/engine/ui/std/

- `__init__.py` — Standard widgets, extracted from what the missions already draw (§6.12). (~179 tok)
- `bottle_hud.py` — BottleHud - the molotov counter strip (M1 + M2; the bodies were identical). (~468 tok)
- `crosshair.py` — Crosshair - the aim reticle shapes (four-arm reticle; combat ring + arms). (~804 tok)
- `dialogue_box.py` — DialogueBox: the shared cutscene dialogue box (A6.11, Phase 4). (~1890 tok)
- `health_bar.py` — HealthBar - the HP strip (panel + "HP" label + ratio bar). (~557 tok)
- `hostiles.py` — Hostiles - the HOSTILES counter box. (~318 tok)
- `minimap.py` — MiniMap - the corner minimap panel. (~6000 tok)
- `objective_banner.py` — ObjectiveBanner - the OBJECTIVE panel. (~777 tok)
- `prompt.py` — prompt - the world-anchored interaction tag ("[E] ...") drawn over a spot. (~950 tok)
- `weapon_panel.py` — WeaponPanel (MagIcons) - the 84px magazine-icon weapon panel. (~1316 tok)

## src/engine/world/

- `__init__.py` — engine.world - entities, components, systems ("ECS-lite", RPE6 §6.4). Facade only; logic lives in the owner modules. (~326 tok)
- `_component.py` — engine.world._component - ``@component`` dataclasses and the schema registry (RPE6 §6.4, A.1). (~1182 tok)
- `entity.py` — engine.world.entity - ``EntityId`` and ``World`` storage (RPE6 §6.4). (~2496 tok)
- `prefab.py` — engine.world.prefab - data-defined entity templates with inheritance (RPE6 §6.4, B.4). (~1600 tok)
- `std.py` — engine.world.std - standard components (RPE6 §6.4). (~1079 tok)
- `system.py` — engine.world.system - ``System`` base, phases and the ``Scheduler`` (RPE6 §6.4, A.1). (~1606 tok)

## src/engine3d/

- `__init__.py` — engine3d - tiny flat-shaded low-poly software renderer for pygame. (~190 tok)
- `core.py` — Core of the low-poly renderer: math, meshes, camera, painter renderer. (~9925 tok)
- `gl.py` — engine3d.gl - GPU backend for the low-poly renderer (ModernGL). (~10478 tok)
- `rig.py` — Low-poly humanoid rig: boxes on a joint hierarchy, posed by angle dicts. (~15925 tok)

## src/entities/

- `__init__.py` — entities package. (~8 tok)
- `adornments.py` — Head gear, as a registry keyed by catalog id. (~2930 tok)
- `art_cache.py` — art_cache.py - Centralized procedural surface cache for Call of Acaristan. (~4469 tok)
- `corpse.py` — Enemy death corpses - bodies that fall instead of vanishing. (~7387 tok)
- `death_anim.py` — Death animation - Option B (Standard). (~5866 tok)
- `enemy_ai.py` — URL configuration (~13522 tok)
- `fallen.py` — A fallen body for a player, drawn in the same visual language as enemies. (~4641 tok)
- `player.py` — Player character: movement, drawing, weapon rig. (~9110 tok)
- `sprite_lib.py` — entities.sprite_lib - deprecated path (RPE6 Phase 2, A-006): see ``engine.assets.sprites``. (~126 tok)
- `weapon_rig.py` — The three weapon rigs, as drawable-on-call functions. (~4423 tok)
- `weapons.py` — Player weapons: pistol, melee, molotov cocktails, fire zones. (~9299 tok)

## src/fx/

- `__init__.py` — fx package. (~6 tok)
- `effects.py` — Visual effects: particles, casings, breach markers, blood decals. (~1615 tok)

## src/game/

- `__init__.py` — Game-owned content (RPE6 Phase 3): art packs under ``game.art`` and pack manifests under (~50 tok)
- `devtools.py` — RPE6 Phase 10 (§6.19): in-game debug tools. (~4243 tok)
- `dialogues.py` — game.dialogues - mission conversation access (RPE6 Phase 7). (~839 tok)
- `input_adapter.py` — RPE6 Phase 9: game-side input adapter (rebinding + gamepad). (~1190 tok)
- `levels.py` — game.levels - level-data access for the missions (RPE6 §6.16, Phase 7). (~514 tok)
- `render3d_bridge.py` — game.render3d_bridge - apply ae.set3d/1 data to a live 3D renderer (RPE6 Phase 8). (~7486 tok)
- `save_adapter.py` — RPE6 Phase 9: game-side adapter between live state and ``engine.save``. (~4305 tok)
- `timelines.py` — game.timelines - cutscene shot-list access (RPE6 Phase 8). (~739 tok)

## src/game/art/

- `__init__.py` — Hand-authored pixel-art packs (pygame-only). ``game.art.m5`` owns the Mission 5 pack; (~43 tok)
- `_layers.py` — Shared helpers for baked world layers (``game.art.<pack>.<name>`` adapter modules). (~637 tok)
- `_pack.py` — Per-pack registry wrappers for game code (``game.art.<pack>``). (~1170 tok)

## src/game/art/m1/

- `__init__.py` — Mission 1 asset pack: baked world layers (and props) of the mission dressing. (~226 tok)
- `exfil_truck.py` — Mission 1 parked KRAP exfil flatbed (shadow, bed, crates, cab, headlights, wheels, KRAP (~230 tok)
- `molotov_icon.py` — HUD Molotov icon (0 active = lit bottle, 1 spent = grey bottle), baked from (~220 tok)
- `pickup_icon.py` — Mission 1 ground-pickup icons (0 magazine, 1 keycard, 2 bandage, 3 bottle), baked from (~235 tok)
- `world_static.py` — Mission 1 static world (office floor grid, container / warehouse walls, desk bodies, bay (~303 tok)

## src/game/art/m2/

- `__init__.py` — Mission 2 asset pack: baked world layers (and props) of the mission dressing. (~226 tok)
- `nest_bits.py` — Pieces of the abandoned Route 12 sniper nest (0 scuff ellipse 48x24, 1 brass casing 8x6, (~251 tok)
- `prop_icon.py` — Mission 2 clue / evidence prop icons at world scale (PROP_WORLD_SCALE), baked from (~366 tok)
- `world_static.py` — Mission 2 static world (road / terrain tiles, static dressing, structure walls, control (~361 tok)

## src/game/art/m3/

- `__init__.py` — Mission 3 asset pack: baked world layers of the prison dressing (and later props). (~228 tok)
- `archives_static.py` — Archives Wing static world baked from ``missions.m3.draw._bake_m3_archives`` (live fallback). (~438 tok)
- `broadcast_static.py` — Broadcast Wing static world baked from ``missions.m3.draw._bake_m3_broadcast`` (live fallback). (~274 tok)
- `camera_body.py` — Mission 3 security-camera mount + smoked dome (0 idle, 1 alerted = opaque dome), baked from (~220 tok)
- `cell_details.py` — Biribel's cell dressing (cot, chair, sink, drain, stains, tally marks, conduit) as a baked (~316 tok)
- `cell_door_blown.py` — Mission 3 interrogation-cell door after the C4 breach has settled: jambs, the two door tiles, (~276 tok)
- `cellblock_static.py` — Cell-block map static world (floors, exterior ground, background dressing, corridor / guard (~567 tok)
- `comms_static.py` — Comms Wing static world baked from ``missions.m3.draw._bake_m3_comms`` (live fallback). (~271 tok)
- `door_tile.py` — Reinforced prison door tile of Mission 3 (frame + leaf / open inner + padlock / LED) in its two (~340 tok)
- `kitchen.py` — Prison kitchen / utility room of the cell block (floor tiles, backsplash, shelves, fixtures, (~379 tok)
- `ko_static.py` — Kill Order ground-floor static world (floors, exterior ground, set dressing: stairwell, dock (~475 tok)
- `pickup_icon.py` — Mission 3 ground-pickup markers (0 looted sidearm, 1 bandage), baked from (~223 tok)
- `wall_monitor.py` — Interrogation-cell wall monitor (Mission 3), baked from (~290 tok)
- `weapon_icon.py` — Mission 3 HUD weapon icons (shiv, chair leg, K-9 SMG, looted sidearm, generic), baked from (~240 tok)

## src/game/art/m4/

- `__init__.py` — Mission 4 asset pack: baked world layers (and props) of the mission dressing. (~226 tok)
- `mag_icon.py` — Mission 4 HUD magazine icons, baked from ``missions.m4.draw._paint_m4_mag_icon`` (live (~337 tok)
- `world_static.py` — Mission 4 static world (floor + walls, buildings, roofs, window grids, storefronts, ground (~390 tok)

## src/game/art/m5/

- `__init__.py` — Mission 5 sprite pack (owner module; ``art.m5`` is the compatibility shim). (~834 tok)
- `_kit.py` — Shared pixel-art kit for the Mission 5 sprites. (~1404 tok)
- `armband.py` — The black Guard armband pinned to the depot notice board (25 x 8 px, 0.5 x 0.16 m): (~229 tok)
- `bale.py` — Strapped newspaper bundles seen from above (Print Works stacks/pallets). (~564 tok)
- `calendar.py` — Safehouse wall calendar (24 x 32 px, 0.6 x 0.8 m): red 1991 header, month (~259 tok)
- `district_map.py` — Vasile's district map (52 x 36 px, 1.3 x 0.9 m): street grid, the river, (~439 tok)
- `guard_banner.py` — Presidential Guard banner (36 x 57 px, 1.2 x 1.9 m): brass rod, black (~631 tok)
- `guard_plate.py` — Lit red Guard notice plate over the Print Works door (36 x 20 px, 0.9 x 0.5 m). (~144 tok)
- `hq_locker.py` — Guard HQ steel locker (26 x 44 px, top-down gameplay prop). The dead man's (~389 tok)
- `inspect_art.py` — Static layers of the Mission 5 "[E] look" first-person shots (canvas (~387 tok)
- `m5_guard.py` — Presidential Guard trooper, top-down gameplay sprite (96 x 96, figure (~695 tok)
- `mag_icon.py` — HUD magazine-icon shells (weapon panel). The shell art is static per kind (~777 tok)
- `mag.py` — Maru's thrown magazines (gameplay). Variant 0: K-9 stick mag (12 x 29 px), (~390 tok)
- `maru.py` — Maru, top-down gameplay sprite (84 x 84, anchor (42, 48) = feet/centre): (~290 tok)
- `plate.py` — HUD status plate (convoy / raid clock), 340 x 46: dark glass, steel rim (~249 tok)
- `portrait_frame.py` — Official portrait of President Retardovici in a gilt frame (30 x 30 px, 1.0 x 1.0 m). (~507 tok)
- `posters.py` — Wall posters of the Lower Quarter (32 x 44 px, 0.64 x 0.88 m in the 3D sets). (~1600 tok)
- `presidential_crest.py` — State crests (40 x 40 px). (~787 tok)
- `press.py` — Print Works offset press, top-down (154 x 64). The press bed is the (~654 tok)
- `printworks_sign.py` — "MAG PRINT WORKS" enamel sign over the Print Works (96 x 14 px, 8.4 x 1.3 m). (~253 tok)
- `tram_wreck.py` — Burnt-out tram on the quarter junction (static decor). One variant at the (~212 tok)
- `wall_posters.py` — Top-down wall posters for the gameplay maps (the wall is seen as its front band). (~680 tok)

## src/game/content/

- `__init__.py` — Pack manifests (``ae.manifest/1``) and palettes, one folder per pack. (~22 tok)

## src/game/content/dialogue/

- `m4.liaison.dlg.json` (~390 tok)
- `m5.maru.dlg.json` (~307 tok)
- `mission0.briefing.dlg.json` (~152 tok)

## src/game/content/grades/

- `cold_blue.grade.json` (~140 tok)
- `faded_stock.grade.json` (~142 tok)
- `night_warm.grade.json` (~141 tok)

## src/game/content/levels/

- `m1.warehouse.level.json` (~648 tok)
- `m2.city.level.json` (~1879 tok)
- `m3.archives.level.json` (~876 tok)
- `m3.broadcast.level.json` (~478 tok)
- `m3.cell.level.json` (~875 tok)
- `m3.comms.level.json` (~874 tok)
- `m3.kill_order.level.json` (~876 tok)
- `m4.station.level.json` (~298 tok)
- `m4.street.level.json` (~657 tok)
- `m5.hq.level.json` (~289 tok)
- `m5.print.level.json` (~310 tok)
- `m5.quarter.level.json` (~525 tok)
- `m5.tunnel.level.json` (~308 tok)
- `mission0.depot.level.json` (~338 tok)

## src/game/content/lighting3d/

- `day_interior.preset.json` (~22 tok)
- `exterior_night_rain.preset.json` (~75 tok)
- `exterior_overcast.preset.json` (~77 tok)
- `night_interior.preset.json` (~74 tok)
- `office_day.preset.json` (~74 tok)
- `rainy_street.preset.json` (~24 tok)

## src/game/content/m1/

- `manifest.json` (~376 tok)

## src/game/content/m2/

- `manifest.json` (~286 tok)

## src/game/content/m3/

- `manifest.json` (~1164 tok)

## src/game/content/m4/

- `manifest.json` (~227 tok)

## src/game/content/m5/

- `manifest.json` (~1087 tok)
- `palette.json` (~153 tok)

## src/game/content/meshes/

- `barrel.mesh.json` (~4156 tok)
- `k93d.mesh.json` (~51474 tok)

## src/game/content/sets/

- `m5.vasile_office.set3d.json` (~2216 tok)
- `mission0.depot.set3d.json` (~1063 tok)
- `mission0.yard.set3d.json` (~756 tok)

## src/game/content/strings/

- `en.json` (~6931 tok)

## src/game/content/textures/

- `asphalt.texture.json` (~170 tok)
- `concrete.texture.json` (~172 tok)
- `wood_crate.texture.json` (~182 tok)

## src/game/content/timelines/

- `core.cutscene1.timeline.json` (~555 tok)
- `core.cutscene2.timeline.json` (~574 tok)
- `m2.ending.timeline.json` (~512 tok)
- `m2.intro.timeline.json` (~311 tok)
- `m2.seby_pickup.timeline.json` (~188 tok)
- `m3.archives_transition.timeline.json` (~240 tok)
- `m3.broadcast_fail.timeline.json` (~236 tok)
- `m3.broadcast_transition.timeline.json` (~331 tok)
- `m3.ending.timeline.json` (~324 tok)
- `m3.intro.timeline.json` (~396 tok)
- `m3.k9_pickup.timeline.json` (~333 tok)
- `m3.ko_transition.timeline.json` (~327 tok)
- `m3.service_transition.timeline.json` (~276 tok)
- `m3.vent_escape.timeline.json` (~149 tok)
- `m3.volkov_mags.timeline.json` (~148 tok)
- `m3.vostral_pickup.timeline.json` (~212 tok)
- `m4.arrest_beats.timeline.json` (~475 tok)
- `m4.ending.timeline.json` (~647 tok)
- `m4.intro.timeline.json` (~229 tok)
- `m4.story_beats.timeline.json` (~246 tok)
- `m5.ending.timeline.json` (~661 tok)
- `m5.intro.timeline.json` (~570 tok)
- `mission0.outro.timeline.json` (~278 tok)

## src/game/render/

- `__init__.py` — game.render - the game's ``engine.render2d`` instance: queue + static layers + post-FX + camera (RPE6 Phase 6). (~604 tok)
- `adapters.py` — Drawable adapters for shared legacy classes (RPE6 Phase 6, ADR-017). (~758 tok)
- `host.py` — game.render.host - the game's render2d instance and the hosted gameplay frame (RPE6 §6.6, Phase 6). (~1055 tok)

## src/game/world/

- `__init__.py` — game.world - the game's ``engine.world`` instance: World + Scheduler + legacy roster (RPE6 Phase 5). (~1521 tok)
- `legacy.py` — game.world.legacy - strangler bridge between the pre-ECS objects and ``engine.world`` (RPE6 §6.4 step 1). (~5262 tok)

## src/missions/

- `__init__.py` — missions package. (~8 tok)
- `arena.py` — Multiplayer arena maps and the deathmatch rules. (~19521 tok)
- `walking_attack3d.py` — True 3D oil-rig strike cinematic, rendered by the game's engine3d. (~12032 tok)
- `walking_sim.py` — Walking sim section: slum exploration, NPCs, firefight overlook panorama. (~42130 tok)

## src/missions/m0/

- `__init__.py` — Mission 0 - Depot - thin host generated by tools/ae_new_mission.py (RPE6 P10). (~3926 tok)
- `enemy_types.json` (~102 tok)

## src/missions/m1/

- `__init__.py` — Package missions/m1 - re-export facade. Parts: map.py, main.py, hotwire.py, update.py, draw.py. (~428 tok)
- `draw.py` — Split from mission.py - see mission.py (shim) for the map. (~22703 tok)
- `hotwire.py` — Split from mission.py - see mission.py (shim) for the map. (~1741 tok)
- `main.py` — Split from mission.py - see mission.py (shim) for the map. (~3223 tok)
- `map.py` — Mission 1 map - authored with core.MapBuilder, baked to list[str]. (~1303 tok)
- `update.py` — Split from mission.py - see mission.py (shim) for the map. (~10459 tok)

## src/missions/m2/

- `__init__.py` — Package missions/m2 - re-export facade. Parts: meta.py, world.py, starts.py, sniper.py, update.py, draw.py. (~1467 tok)
- `components.py` — Mission 2 entity components (RPE6 Phase 5, D4). (~160 tok)
- `draw.py` — Split from mission2.py - see mission2.py (shim) for the map. (~110670 tok)
- `meta.py` — Split from mission2.py - see mission2.py (shim) for the map. (~7805 tok)
- `sniper.py` — Split from mission2.py - see mission2.py (shim) for the map. (~25924 tok)
- `sniper3d_set.py` — Route 12 toll plaza, built for the low-poly sniper cinematic. (~3732 tok)
- `sniper3d.py` — Mission 2 - "Route 12 Kill-Box": the sniper ambush as a low-poly 3D film. (~16640 tok)
- `starts.py` — Split from mission2.py - see mission2.py (shim) for the map. (~7939 tok)
- `update.py` — Split from mission2.py - see mission2.py (shim) for the map. (~17464 tok)
- `world.py` — Split from mission2.py - see mission2.py (shim) for the map. (~11402 tok)

## src/missions/m3/

- `__init__.py` — Package missions/m3 - re-export facade. Parts: meta.py, maps.py, world.py, flow.py, interrog.py, systems.py, draw.py. (~86254 tok)
- `components.py` — Mission 3 entity components (RPE6 Phase 5, D4). (~752 tok)
- `draw.py` — Split from mission3.py - see mission3.py (shim) for the map. (~117532 tok)
- `flow.py` — Split from mission3.py - see mission3.py (shim) for the map. (~22902 tok)
- `interrog.py` — Split from mission3.py - see mission3.py (shim) for the map. (~7726 tok)
- `maps.py` — Split from mission3.py - see mission3.py (shim) for the map. (~8965 tok)
- `meta.py` — Split from mission3.py - see mission3.py (shim) for the map. (~7918 tok)
- `sweep.py` — Slice 5b-5d: the Kill Order sweep director, overwatch pin, Volkov (~13662 tok)
- `systems.py` — Split from mission3.py - see mission3.py (shim) for the map. (~53970 tok)
- `world.py` — Split from mission3.py - see mission3.py (shim) for the map. (~28380 tok)

## src/missions/m4/

- `__init__.py` — Mission 4: The Aftermath - the world after the broadcast. (~1108 tok)
- `components.py` — Mission 4 entity components (RPE6 Phase 5, D4). (~171 tok)
- `draw.py` — Split from mission4.py - see __init__.py for the package facade. (~34421 tok)
- `flow.py` — Split from mission4.py - see __init__.py for the package facade. (~7542 tok)
- `maps.py` — Split from mission4.py - see __init__.py for the package facade. (~5400 tok)
- `meta.py` — Mission 4 - part module. See __init__.py for the package facade. (~2782 tok)
- `systems.py` — Split from mission4.py - see __init__.py for the package facade. (~4365 tok)
- `world.py` — Split from mission4.py - see __init__.py for the package facade. (~7252 tok)

## src/missions/m5/

- `__init__.py` — Mission 5: Martial Law - the capital under emergency rule. (~869 tok)
- `components.py` — Mission 5 entity components (RPE6 Phase 5, D4). (~379 tok)
- `decor_interior.py` — decor_interior.py - Mission 5 interior set dressing (gauntlet pass). (~6252 tok)
- `decor_paint.py` — decor_paint.py - Mission 5 static set dressing painters (round 2). (~6168 tok)
- `decor.py` — decor.py - Mission 5 set dressing, lighting and inspectables (round 2). (~4388 tok)
- `draw.py` — Mission 5 - part module. See __init__.py for the package facade. (~18736 tok)
- `finale_audio.py` — Mission 5 sound design and cutscene-owned playback. (~2930 tok)
- `finale_script.py` — M5 rebuilt finale: immutable script/timing shared by renderer and player. (~642 tok)
- `flow.py` — Mission 5 - part module. See __init__.py for the package facade. (~6157 tok)
- `inspect_art_street.py` — inspect_art_street.py - storeroom + Lower Quarter inspect shots (~3928 tok)
- `inspect_art.py` — inspect_art.py - painters for the Mission 5 first-person inspect shots. (~4634 tok)
- `inspect_fpv.py` — inspect_fpv.py - Mission 5 "[E] look": a short first-person look at the (~2335 tok)
- `maps.py` — Mission 5 - part module. See __init__.py for the package facade. (~3018 tok)
- `meta.py` — Mission 5 - part module. See __init__.py for the package facade. (~3706 tok)
- `quarter.py` — quarter.py - Lower Quarter systems (round 2): turns 'run and gun' into a run (~6102 tok)
- `render.py` — Mission 5 - part module. RENDER_SUBMIT systems (RPE6 §6.4 step 2 / §6.6, Phase 6). (~1512 tok)
- `systems.py` — Mission 5 - part module. See __init__.py for the package facade. (~4084 tok)
- `tram_wreck.py` — M5 Lower Quarter: the burning tram wreck (top-down). (~6728 tok)
- `water.py` — M5 shallow floodwater: one connected, world-space surface, never tile stamps. (~1315 tok)
- `world.py` — Mission 5 - part module. See __init__.py for the package facade. (~7591 tok)

## src/missions/m6/

- `__init__.py` — Mission 6: Black Notebook - re-export facade (load order = parts order). (~594 tok)
- `decor.py` — Mission 6 - stage decor, ground art and night lighting. (~13324 tok)
- `draw.py` — Mission 6 gameplay renderer. (~4682 tok)
- `flow.py` — Mission 6 - stage ladder, checkpoints and the ending handoff. (~3453 tok)
- `hud3d.py` — Mission 6 3D HUD: minimal tactical, shared by the train shootout and the (~3045 tok)
- `m6_audio.py` — Mission 6 sound design: film stems, foley and the interactive-train bed. (~6215 tok)
- `maps.py` — Authored map layer for Mission 6 - three distinct playable spaces. (~2240 tok)
- `meta.py` — Mission 6 metadata, stage constants and authored cutscene timelines. (~3000 tok)
- `stealth.py` — Mission 6 - floodlight stealth for no-man's-land and the rail yard. (~3989 tok)
- `systems.py` — Mission 6 - per-frame gameplay pipeline. (~2860 tok)
- `train3d.py` — Mission 6 - the interactive 3D train scene (``docs/MISSION6_PLOT.md``). (~64975 tok)
- `world.py` — Mission 6 - world construction, Guard spawns and shared helpers. (~3755 tok)
- `yard3d.py` — Mission 6 - "Who fired?": the third-person fight after Volkov's death. (~18258 tok)

## src/net/

- `__init__.py` — net - multiplayer relay client. Parts: protocol.py, client.py. (~285 tok)
- `client.py` — Game-side client for the KRAPNET master server. (~4646 tok)
- `discovery.py` — LAN auto-discovery for the master server. (~511 tok)
- `match.py` — A multiplayer match session: authoritative host + interpolating clients. (~4524 tok)
- `portmap.py` — Automatic router port forwarding (UPnP IGD + NAT-PMP), stdlib only. (~7430 tok)
- `protocol.py` — Wire protocol for the Acaristan multiplayer master server. (~14266 tok)
- `roomcode.py` — Short, game-branded room codes for direct arena matches. (~1552 tok)
- `tcp_tunnel.py` — Public raw-TCP tunnels for arena matches. (~2992 tok)

## src/tools/

- `input_recorder.py` — Dev-only gameplay input recorder (RPE6 Phase 0, replay baselines). (~658 tok)
- `ko_playability_audit.py` — Kill Order (Mission 3 Phase 5) playability audit - headless. (~6104 tok)
- `trailer_bot.py` — Trailer bot - deterministic operator driver for cinematic capture. (~2250 tok)

## src/ui/

- `__init__.py` — Package ui - re-export facade. Parts: widgets.py, main.py, mp.py, system.py. (~1234 tok)
- `arena_view.py` — Renderer for multiplayer arena matches. (~25079 tok)
- `hud.py` — HUD overlays: minimap, safe keypad, notebook inspection, desk notes. (~16406 tok)
- `main.py` — Split from menu.py - see menu.py (shim) for the map. (~9349 tok)
- `match_screen.py` — The in-game arena match: entry panel plus the live match runtime. (~50757 tok)
- `mission_failed.py` — Mission-specific failure terminals with bespoke procedural illustrations. (~3971 tok)
- `mp.py` — Split from menu.py - see menu.py (shim) for the map. (~25518 tok)
- `multiplayer_style.py` — Read-only KRAPNET presentation. No sockets, timers or session mutations. (~4663 tok)
- `pixfont.py` — Pixel bitmap fonts for the radio UI (polish pass T6b). (~3560 tok)
- `radio.py` — Radio transmission widget (polish pass T6, field-radio restyle T6b). (~8171 tok)
- `shop.py` — The Outfitter - spend Acaribucks on the loadout you play the arena in. (~7496 tok)
- `system.py` — Split from menu.py - see menu.py (shim) for the map. (~15120 tok)
- `upload_os.py` — Upload OS - a retro CRT terminal operating system for the evidence upload. (~40384 tok)
- `widgets.py` — Split from menu.py - see menu.py (shim) for the map. (~4153 tok)

## tests/

- `__init__.py` (~0 tok)

## tests/api/

- `engine_api.json` (~49834 tok)

## tests/data/

- `m5_scene_trace.txt` — RPE6 §6.2 acceptance trace — Mission 5 flow as mirrored from the legacy FSM (A-005). (~263 tok)

## tests/golden/baseline_v0/

- `manifest.json` (~47017 tok)

## tests/loop/baseline_v0/

- `boot.json` (~4628 tok)
- `m1.json` (~6576 tok)
- `m2.json` (~6580 tok)
- `m3.json` (~6580 tok)
- `m4.json` (~6580 tok)
- `m5.json` (~6580 tok)
- `walk.json` (~6586 tok)

## tests/loop/baseline_v1/

- `boot.json` (~4388 tok)
- `m1.json` (~6234 tok)
- `m2.json` (~6237 tok)
- `m3.json` (~6237 tok)
- `m4.json` (~6237 tok)
- `m5.json` (~6237 tok)
- `walk.json` (~6242 tok)

## tests/loop/baseline_v2/

- `boot.json` (~4388 tok)
- `m1.json` (~6234 tok)
- `m2.json` (~6237 tok)
- `m3.json` (~6237 tok)
- `m4.json` (~6237 tok)
- `m5.json` (~6237 tok)
- `walk.json` (~6242 tok)

## tests/loop/baseline_v3/

- `boot.json` (~4407 tok)
- `m1.json` (~6243 tok)
- `m2.json` (~6246 tok)
- `m3.json` (~6246 tok)
- `m4.json` (~6246 tok)
- `m5.json` (~6246 tok)
- `walk.json` (~6262 tok)

## tests/loop/baseline_v4/

- `boot.json` (~4407 tok)
- `m1.json` (~6243 tok)
- `m2.json` (~6246 tok)
- `m3.json` (~6246 tok)
- `m4.json` (~6246 tok)
- `m5.json` (~6246 tok)
- `walk.json` (~6262 tok)

## tests/loop/baseline_v5/

- `boot.json` (~4407 tok)
- `m1.json` (~6243 tok)
- `m2.json` (~6246 tok)
- `m3.json` (~6246 tok)
- `m4.json` (~6246 tok)
- `m5.json` (~6246 tok)
- `walk.json` (~6262 tok)

## tests/loop/baseline_v6/

- `boot.json` (~4427 tok)
- `m1.json` (~6243 tok)
- `m2.json` (~6246 tok)
- `m3.json` (~6246 tok)
- `m4.json` (~6246 tok)
- `m5.json` (~6246 tok)
- `walk.json` (~6262 tok)

## tests/replay/baseline_v0/

- `m1.fields.json` (~5893 tok)
- `m1.json` (~1852 tok)
- `m2.fields.json` (~25981 tok)
- `m2.json` (~1778 tok)
- `m3.fields.json` (~26558 tok)
- `m3.json` (~1781 tok)
- `m4.fields.json` (~13822 tok)
- `m4.json` (~1778 tok)
- `m5.fields.json` (~18348 tok)
- `m5.json` (~1818 tok)

## tests/replay/baseline_v1/

- `m1.fields.json` (~6928 tok)
- `m1.json` (~1852 tok)
- `m2.fields.json` (~26660 tok)
- `m2.json` (~1778 tok)
- `m3.fields.json` (~28755 tok)
- `m3.json` (~1781 tok)
- `m4.fields.json` (~13827 tok)
- `m4.json` (~1778 tok)
- `m5.fields.json` (~19219 tok)
- `m5.json` (~1818 tok)

## tests/replay/baseline_v2/

- `m1.fields.json` (~7080 tok)
- `m1.json` (~1852 tok)
- `m2.fields.json` (~26813 tok)
- `m2.json` (~1778 tok)
- `m3.fields.json` (~28908 tok)
- `m3.json` (~1781 tok)
- `m4.fields.json` (~15010 tok)
- `m4.json` (~1778 tok)
- `m5.fields.json` (~19370 tok)
- `m5.json` (~1818 tok)

## tests/unit/

- `__init__.py` (~0 tok)
- `_helpers.py` — Shared test setup: put ``src`` on sys.path and keep SDL headless. (~194 tok)
- `_path.py` (~51 tok)
- `test_anim_props.py` — Phase 11 step 10: flicker is a deterministic closed form; set fields (~705 tok)
- `test_app_boot_crash.py` — engine.core.App: headless boot, service wiring, crash report (§6.1 acceptance). (~1464 tok)
- `test_art_cache.py` — art_cache.get_plate_bg: the shared M4/M5 "status plate" chrome. (~469 tok)
- `test_assets_registry.py` — engine.assets Phase 3: manifest schema, registry chain + cache + ref-counts, bake/check (~5220 tok)
- `test_cast_shadows.py` — Phase 11 step 7 (ADR-023): baked cast shadows - occluded faces darken, (~619 tok)
- `test_clock.py` — engine.core.Clock: fixed-step semantics, identity with the legacy FixedStepClock (ADR-004). (~1940 tok)
- `test_devtools.py` — RPE6 Phase 10 (§6.19): debug overlay / inspector data builders + console commands. (~1005 tok)
- `test_engine_boot.py` — App.boot display ownership (ADAPTER A-001). (~626 tok)
- `test_engine_core.py` — Unit tests for engine.core (stdlib unittest; run: python -m unittest discover -s tests/unit -t .). (~1883 tok)
- `test_engine_dialogue_box.py` — engine.ui.std.dialogue_box (Phase 4): theme injection, slide ownership. (~1116 tok)
- `test_engine_level_dialogue.py` — engine.level + engine.dialogue kernels: load/validate, Tiled import, runner conditions/effects (RPE6 Phase 7). (~1953 tok)
- `test_engine_render2d.py` — engine.render2d kernel: queue order, drawables, rotation cache, camera, static chunks, post-FX parity (RPE6 Phase 6). (~4079 tok)
- `test_engine_settings_save_input.py` — engine.settings / engine.save / engine.input kernels (RPE6 Phase 9). (~1730 tok)
- `test_engine_shims.py` — A-006 shims: the legacy paths re-export the engine implementations unchanged. (~924 tok)
- `test_engine_text.py` — engine.text Phase 4: string tables + `T()`, font registry + glyph coverage, layout (~2638 tok)
- `test_engine_timeline_set3d.py` — engine.timeline + engine.render3d kernels: expressions, sampling, set building (RPE6 Phase 8). (~1547 tok)
- `test_engine_ui.py` — engine.ui Phase 4: Theme + the standard widgets, drawn headless. (~1698 tok)
- `test_engine_world.py` — engine.world kernel: registry, storage, views, queries, scheduler phases, prefabs (RPE6 Phase 5). (~2572 tok)
- `test_events_log_services.py` — engine.core: EventBus (§6.3), Log (§6.23), Services and Settings (§6.1). (~1397 tok)
- `test_faces3d.py` — Phase 11 step 8: expressions rebuild only the face, mouth flap is a (~814 tok)
- `test_game_dialogues.py` — game.dialogues converter: node chain -> legacy beat dicts (RPE6 Phase 7). (~814 tok)
- `test_game_world_bridge.py` — game.world bridge (RPE6 Phase 5, D4): ensure/get, roster reset + removed-tag policy, WalkCycle.advance. (~2622 tok)
- `test_gl_composite.py` — GL renderer item-queue regression (owner-hardware crash, M5 finale). (~1311 tok)
- `test_m5_ending.py` — M5 finale regressions. Run: python -m unittest tests.unit.test_m5_ending -v. (~2231 tok)
- `test_m5_finale_audio.py` — Focused M5 sound/lifecycle regressions, without starting app or saves. (~3099 tok)
- `test_m6_campaign.py` — Mission 6 campaign regressions. Run: python -m unittest tests.unit.test_m6_campaign -v. (~13148 tok)
- `test_mathx_profiling.py` — engine.core.mathx and Profiler. (~479 tok)
- `test_mesh_import.py` — Phase 11 step 11 (ADR-024): the importer converts OBJ/glTF into (~1402 tok)
- `test_phase1_rng_imports.py` — Phase 1 checks: legacy rng stream (R6) and m3 import side effects (B-010). (~641 tok)
- `test_post3d.py` — RPE6 Phase 11 step 5: cinematic post stack (cutscenes.post3d). (~784 tok)
- `test_presets.py` — RPE6 Phase 11 step 1: lighting preset resolution (engine.render3d). (~843 tok)
- `test_render_adapters.py` — Phase 6 peel-off twins are pixel-identical to the legacy painters they replace (RPE6, ADR-017). (~3061 tok)
- `test_render3d_p11.py` — RPE6 Phase 11: local lights, contact shadows, baked AO (data -> bridge). (~620 tok)
- `test_rng.py` — engine.core.rng: named streams are independent, seeded, snapshot-able (R6, B-002). (~925 tok)
- `test_scene_mirror.py` — core.scene_mirror (A-005): the legacy FSM replayed onto an engine SceneStack. (~1171 tok)
- `test_scene_stack.py` — engine.scene: lifecycle, overlay/passthrough dispatch, deferred mutations, trace (§6.2). (~1751 tok)
- `test_scene_types.py` — engine.scene.CutsceneScene / InspectScene (§6.2) and the mirror's scene factory (A-007). (~1645 tok)
- `test_textures3d.py` — Phase 11 step 9: palette textures load through the bridge, UV (~916 tok)
- `test_timeline_edit_scene.py` — Phase 8 tooling surface: ae_timeline_edit round-trip + CutsceneScene.from_timeline. (~718 tok)
- `test_voice_timing.py` — Voice clip timing must not depend on SDL's decoded length (asset diet, 2026-10-14). (~2138 tok)
- `test_weather3d.py` — Phase 11 step 6: weather is a closed-form, seeded, quality-gated (~616 tok)

## tools/

- `.build_settings.json` (~19 tok)
- `ae_api_snapshot.py` — ae_api_snapshot.py - public API snapshot of ``src/engine`` (RPE6 Phase 2 gate). (~2134 tok)
- `ae_audit.py` — RPE6 Phase 0 audit: static census of src/ and tools/ (read-only, stdlib only). (~7154 tok)
- `ae_bake.py` — ae_bake - bake / check / lint content packs (RPE6 Phase 3, §6.5). (~1364 tok)
- `ae_bench.py` — ae_bench.py - frame budget bench (RPE6 §6.22; Phase 6 exit evidence). (~1873 tok)
- `ae_bench3d.py` — AE BENCH3D - 3D frame budget bench (RPE6 Phase 11 exit evidence). (~1252 tok)
- `ae_ci.py` — RPE6 one-command CI (D10).  python tools/ae_ci.py [--quick] [--skip name,name] [--jobs N] [--serial] [--force] (~2970 tok)
- `ae_d4_gate.py` — ae_d4_gate.py - D4 grep gate: no attribute stuffing on entity objects (RPE6 §2 D4, §6.4 acceptance). (~1868 tok)
- `ae_d4_replay_compat.py` — ae_d4_replay_compat.py - proof that moving entity data into components kept behaviour (RPE6 Phase 5). (~1663 tok)
- `ae_d6_gate.py` — ae_d6_gate.py - D6 gate: one 2D render path (RPE6 §2 D6, §6.6; Phase 6). (~2000 tok)
- `ae_dialogue_check.py` — ae_dialogue_check - Phase 7 dialogue gate: validate + data == legacy tables. (~934 tok)
- `ae_dialogue_export.py` — ae_dialogue_export - write the legacy conversation tables as ae.dialogue/1 data. (~1094 tok)
- `ae_draw_audit.py` — ae_draw_audit - procedural-draw census per mission (RPE6 Phase 3, P3-M3). (~2081 tok)
- `ae_dump_components.py` — ae_dump_components.py - component census of a running mission stage (RPE6 §6.4 acceptance). (~1321 tok)
- `ae_engine3d_parity.py` — AE ENGINE3D PARITY - software-backend determinism evidence. (~773 tok)
- `ae_flash_check.py` — ae_flash_check - Phase 9 exit evidence: flash reduction caps the breach white-out. (~596 tok)
- `ae_gauntlet.py` — AE GAUNTLET - render everything once at offsets nobody tested. (~1256 tok)
- `ae_global_names.py` — ae_global_names - unresolved global references in src (Phase 4 gate, A-001). (~1397 tok)
- `ae_golden.py` — RPE6 golden-image harness (master prompt §9). Phase 0: capture + verify. (~6310 tok)
- `ae_hud_census.py` — ae_hud_census - HUD duplication census across missions (Phase 4 prep). (~2404 tok)
- `ae_import_check.py` — RPE6 import side-effect check (R7, §6.1 acceptance). (~1069 tok)
- `ae_import_k93d.py` — AE IMPORT K93D - the first authored 3D weapon asset (assets/3D/K93D.glb). (~3720 tok)
- `ae_import_mesh.py` — AE IMPORT MESH - Blender/glTF/OBJ -> ae.mesh/1 asset (ADR-024). (~2183 tok)
- `ae_layer_parity.py` — Parity oracle for baked *chunk* layers (``game.art.<pack>.<name>`` adapters with ``bake_setup``): (~1175 tok)
- `ae_layer_probe.py` — ae_layer_probe - can this camera-space painter become a baked world layer? (~2358 tok)
- `ae_level_check.py` — ae_level_check.py - validator: level JSON == legacy generator output (RPE6 P7). (~766 tok)
- `ae_level_export.py` — ae_level_export.py - export the legacy mission grids to .level.json (RPE6 P7-M2). (~1326 tok)
- `ae_loop.py` — RPE6 loop probe: drive the REAL app.py main loop headless and hash every frame. (~7711 tok)
- `ae_migrate_time.py` — RPE6 B-001: move legacy wall-clock reads onto the engine timebase. (~1782 tok)
- `ae_mission0_check.py` — .py tree hash equals the baseline frozen (~1874 tok)
- `ae_narrow_star.py` — ae_narrow_star - rewrite ``from core.config import *`` into explicit imports (A-001, Phase 4). (~1274 tok)
- `ae_new_mission.py` — ae_new_mission.py - scaffold a new RPE6 mission (Phase 10, §7/D2). (~5093 tok)
- `ae_normalize.py` — RPE6 Phase 0 item 7: line-ending / encoding normalisation with proofs (R14, B-003). (~2461 tok)
- `ae_package.py` — AE PACKAGE - build the distributable game zip. (~998 tok)
- `ae_proof_sheet.py` — AE PROOF SHEET - side-by-side before/after sheet for Phase 11 steps. (~845 tok)
- `ae_proof3d.py` — AE PROOF3D - render the fixed Phase 11 proof scenes to PNGs. (~1867 tok)
- `ae_reexport_check.py` — ae_reexport_check - who pulls star-imported names THROUGH another module? (Phase 4, A-001) (~1238 tok)
- `ae_replay_check.py` — RPE6 Phase 9 exit tool: engine-save snapshots reproduce replay state. (~960 tok)
- `ae_replay.py` — RPE6 replay baseline + determinism check (master prompt §6.17, Phase 0 item 9, D8). (~3776 tok)
- `ae_set3d_check.py` — ae_set3d_check - Phase 8 set gate: validate + build every .set3d.json. (~623 tok)
- `ae_star_imports.py` — ae_star_imports - inventory of ``from core.config import *`` users (A-001 prep, Phase 4). (~1774 tok)
- `ae_text_check.py` — ae_text_check.py - string-table validation and text fit (RPE6 Phase 4, 6.13). (~4332 tok)
- `ae_textures_gen.py` — AE TEXTURES GEN - deterministic palette textures (RPE6 Phase 11 step 9). (~826 tok)
- `ae_timeline_check.py` — ae_timeline_check - Phase 8 timeline gate: validate + data == legacy tables. (~1287 tok)
- `ae_timeline_edit.py` — ae_timeline_edit - the Phase 8 camera/track key editor (CLI form). (~986 tok)
- `ae_timeline_export.py` — ae_timeline_export - write the legacy cutscene shot lists as ae.timeline/1 data. (~1384 tok)
- `ae_validate.py` — AE VALIDATE - load every game data file through its public loader. (~753 tok)
- `assemble_final_trailer.py` — assemble_final_trailer.py - Post-production assembler for CALL OF ACARISTAN. (~9580 tok)
- `bake_m5_sprites.py` — Compatibility wrapper: the Mission 5 bake moved to the generic pipeline. (~134 tok)
- `bench_budgets.json` (~1554 tok)
- `build_all_sprites.py` — Rebuild every generated art asset in one go (Polish T7). (~636 tok)
- `build_code_pdf.py` — CodePDF: find_py_files, sort_key, find_unicode_mono_font, add_page + 13 more (~13060 tok)
- `build_code_txt.py` — find_py_files, write_files_to_txt, write_individual_txts, resolve_cli_files + 8 more (~2767 tok)
- `build_host_exe.bat` (~294 tok)
- `build_join_exe.bat` (~235 tok)
- `build_sfx_stem.py` — build_sfx_stem.py - render trailer_sfx_stem.wav from captured foley logs. (~6218 tok)
- `build_windows.py` — Build the Windows game as a PyInstaller --onedir bundle (no admin needed). (~752 tok)
- `cast_lineup.py` — 3D cast line-up: python tools/cast_lineup.py [body|face] [out.jpg] [key ...] (~1042 tok)
- `cast_sheet.py` — Cast sheets: the 2D cutscene figures (figure_kit) beside their 3D rigs. (~1931 tok)
- `check_boundaries.py` — RPE6 boundary lint (master prompt §5.3, D1). (~1779 tok)
- `convert_voice_ogg.py` — /*.wav to OGG Vorbis in place (RPE6 housekeeping, 2026-10-14). (~647 tok)
- `debug_stem.py` — Standalone timing run of mp_trailer_assemble.render_foley_stem. (~262 tok)
- `dev_panel.py` — dev_panel.py - clickable dev control panel for jumping into missions. (~7800 tok)
- `download_bore.py` — Fetch the pinned official Windows x64 bore release for PyInstaller builds. (~490 tok)
- `engine3d_check.py` — GPU vs software renderer check on the real M2 ambush film. (~1360 tok)
- `export_m5_audio.py` — Export the exact procedural M5 mix for audition; no app launch/saves. (~634 tok)
- `finale_compare.py` — Side-by-side probe: M2 ambush film (sniper3d) vs M5 finale (m5shadow3d). (~734 tok)
- `finale_gait_check.py` — M5 finale gait check: Maru timing, footstep contact times, world foot drift. (~585 tok)
- `finale_probe.py` — Render M5 finale frames (optionally from custom cameras) into a JPEG contact sheet. (~559 tok)
- `gen_barrel_obj.py` — Generate assets/import/barrel.obj - a low-poly barrel (10 sides, (~706 tok)
- `golden.json` (~2904 tok)
- `golden.py` — golden.py - golden-image regression gate for the reworked renderer. (~1056 tok)
- `join_lobby.bat` — Declares to (~124 tok)
- `k9_pickup_check.py` — Headless regression checks and optional preview for the K-9 pickup. (~1933 tok)
- `m5_cinematic_polish_check.py` — Regression evidence for the M5 noir polish; safe isolated preview only. (~1178 tok)
- `m5_contact_sheets.py` — Build labelled contact sheets + automatic frame stats from previews/m5_encounter_review. (~579 tok)
- `m5_cut_check.py` — Round-2 M5 cutscene check: renders every m5x_ take (3D, then 2D fallback). (~371 tok)
- `m5_draw_audit.py` — Compatibility wrapper: the per-mission draw census is tools/ae_draw_audit.py. (~121 tok)
- `m5_dump.py` (~188 tok)
- `m5_encounter_review.py` — Deterministic M5 preview suite. python tools/m5_encounter_review.py [capture|test|export OFFSET] (~2400 tok)
- `m5_ending_stage_check.py` — Ending staging/weapon regressions and native-size visual probes; safe saves. (~2909 tok)
- `m5_feedback_check.py` — Focused M5 feedback regressions and visual evidence, without touching saves. (~2350 tok)
- `m5_finale_cut_check.py` — Focused check for retiring the M5 finale without losing campaign completion. (~1928 tok)
- `m5_fx_check.py` — M5 FX checks: reduced motion zeroes handheld/shake/roll; 2D fallback still works. (~730 tok)
- `m5_gauntlet_cycle.py` — M5 visual gauntlet - one full cutscene render cycle at delivery resolution. (~2003 tok)
- `m5_gauntlet_sheet.py` — Compact WebP contact sheet for remote VLM review. (~534 tok)
- `m5_gauntlet_shots.py` — M5 gauntlet: render every Mission 5 surface we review (top-down stages, (~1094 tok)
- `m5_harbour_art_check.py` — M5 harbour pass guard: the cubical cast and the choreography are pinned, art is validated. (~1191 tok)
- `m5_laser_stair_check.py` — M5 laser integration and stair landing regression, both renderer backends. (~787 tok)
- `m5_probe.py` — m5_probe.py - render M5 cutscene frames headless for visual review. (~532 tok)
- `m5_r2_check.py` — Round-2 M5 headless check: builds stages, draws a few frames, saves PNGs. (~559 tok)
- `m5_rifle_clearance.py` — Weapon clearance against actual torso/head/pelvis box meshes, plus grip reach. (~728 tok)
- `m5_shadow_check.py` — Fresh M5 3D finale: geometry, timing, actual app player and save handoff. (~4755 tok)
- `m5_sheet.py` — Contact sheet for review: python tools/m5_sheet.py out.jpg name1 name2 ... (~404 tok)
- `m5_shots.py` — M5 3D cutscene stills + timing: python tools/m5_shots.py OUT_DIR [scene_prefix] (~753 tok)
- `m5_sprite_review.py` — Montage of selected baked M5 sprites for review. (~396 tok)
- `m5_stair_room_check.py` — Regression: interiors cover the frame and both stair actors remain visible. (~902 tok)
- `m5_view_export.py` — Pack review images for remote viewing: prints one JSON line per image (~534 tok)
- `m6_shots.py` — M6 3D film + interactive train stills. (~3139 tok)
- `make_art_pack.py` — make_art_pack.py - author assets/art/*.png (phases 1, 2, 4 art). (~14776 tok)
- `make_short_branded.py` — make_short_branded.py - branded 9:16 vertical Short from the final master. (~2596 tok)
- `make_short_clean.py` — make_short_clean.py - 9:16 vertical Short from the final master. (~984 tok)
- `make_station_sprites.py` — make_station_sprites.py - author the hero-interactable sprites. (~1939 tok)
- `mp_arena_duo.py` — Launch TWO full game windows already sitting in the multiplayer arena. (~1011 tok)
- `mp_bot.py` — Headless fake player, for testing multiplayer on ONE PC. (~1382 tok)
- `mp_choreo_probe.py` — mp_choreo_probe.py - gate the MP trailer fight headlessly before capturing. (~2945 tok)
- `mp_host_main.py` — PyInstaller entry point for the self-hosted lobby EXE. (~231 tok)
- `mp_host.py` — Self-hosted KRAPNET server for Call of Acaristan. (~2988 tok)
- `mp_join.py` — Join a friend's Call of Acaristan lobby and chat. No game required. (~1817 tok)
- `mp_match.py` — Play a real multiplayer arena match. This is the whole stack in one file. (~4500 tok)
- `mp_remaster.py` — Re-master audio only: reuse the kept premix.wav, re-run normalise + mux. (~366 tok)
- `mp_server.py` — Standalone KRAPNET master server for Call of Acaristan. (~6038 tok)
- `mp_trailer_assemble_tiktok.py` — 9:16 TikTok cut of the multiplayer announcement. (~9483 tok)
- `mp_trailer_assemble.py` — mp_trailer_assemble.py - post-production assembler for the MULTIPLAYER (~9899 tok)
- `mp_trailer_capture.py` — mp_trailer_capture.py - REAL multiplayer arena footage for the announcement trailer. (~23941 tok)
- `oilrig_preview.py` — Off-screen preview of the oil-rig strike cinematic (missions.walking_attack3d). (~1287 tok)
- `overlay_cleanup.py` — Tidy a project root after pasting the slim overlay zip over an older checkout. (~854 tok)
- `preflight_bot_test.py` — Offline pre-flight: exercise GridNav + ArenaBot + foley payloads against (~809 tok)
- `preview_mission_failed.py` — Render/test all failure terminals; --show opens a safe, save-free gallery. (~2000 tok)
- `record_fresh_action.py` — record_fresh_action.py - clean standalone combat capture. (~12111 tok)
- `render_ko_video.py` — Headless cinematic trailer bot, PLAN_2 cut. (~3308 tok)
- `render_m4_ending.py` — Render the real M4 cutscene player safely, without importing app's loop. (~3026 tok)
- `render_m5_ending.py` — Render M5 with the production cutscene player, using the safe M4 capture kit. (~940 tok)
- `render_m5_shadow.py` — Capture the production M5 finale at 30 fps with native ambience/foley. (~1324 tok)
- `render_m5_stair.py` — Export the complete updated M5 stair shot with its production sound cues. (~1060 tok)
- `render_trailer_v2.py` — render_trailer_v2.py - cinematic finish wrapper over render_trailer.py. (~7215 tok)
- `render_trailer.py` — render_trailer.py - 75-90s MP4 game trailer (headless real gameplay). (~7770 tok)
- `setup_env.ps1` (~183 tok)
- `shot_fail_screens.py` — Polish pass T9 evidence: render the Mission Failed screen for M1-M5. (~371 tok)
- `shot_m5x.py` — Polish pass evidence helper: render M5X 3D cutscene frames to PNG. (~590 tok)
- `shot_outfit.py` — Polish pass Task 5 evidence: Biribel's M5 Guard kit in every view. (~1462 tok)
- `shot_radio.py` — Polish pass Task 6 evidence: the radio transmission widget in every mission. (~2468 tok)
- `shot_weapon_grid.py` — Polish pass Task 4: weapon-attachment verification grid. (~1229 tok)
- `slim_tree.py` — slim_tree.py - remove dead weight from the project root (dry run by default). (~2532 tok)
- `smoke_test.py` — Must be set before pygame/config import. (~125972 tok)
- `test_multiplayer_ui.py` — Small presentation regression suite; no live networking or external service. (~1178 tok)
- `test_oilrig_collapse.py` — Geometry and effect regressions for the rig collapse repair. (~1827 tok)
- `test_tcp_tunnel.py` — Fast stdlib-only tunnel regression tests (no pygame or internet required). (~1093 tok)
- `voice_audit.py` — Voice-line audit (polish pass T1). (~6258 tok)
- `zip_project.py` — Zip this project into a single archive, optionally uploading it to Pixeldrain. (~5342 tok)

## tools/sprites/

- `compare_shots.py` — compare_shots.py - stitch T7 before/after shots side by side. (~451 tok)
- `fx.py` — fx.py - Mission 2 tanker-blast aftermath as sprites (Polish T7). (~2187 tok)
- `inventory.py` — Procedural-art inventory (Polish Task 7, step 1). (~2788 tok)
- `kit.py` — kit.py - shared machinery for the tools/sprites/<family>.py generators. (~2580 tok)
- `mission_failed.py` — Bespoke, entirely code-drawn mission-failure vignettes. (~5185 tok)
- `palette.py` — palette.py - the locked house palette shared by every tools/sprites generator. (~1030 tok)
- `portrait_refs.py` — portrait_refs.py - check the radio portraits against the cutscene cast. (~978 tok)
- `portraits.py` — portraits.py - radio caller-ID portraits (polish pass T6b). (~12549 tok)
- `props.py` — props.py - Mission 2 story props + the upload terminal as sprites (Polish T7). (~3441 tok)
- `status.json` (~287 tok)
- `t7_probe.py` — t7_probe.py - before/after shots + draw-time probe for Polish T7. (~1799 tok)
- `vehicles.py` — vehicles.py - Mission 2 road vehicles as authored sprite sheets (Polish T7). (~5959 tok)

## tools/trailer3d/

- `common.py` — Shared trailer helpers: renderer setup, camera keys, 2D light/rain/grain FX, (~4287 tok)
- `music_cut.py` — Cut 'Shell Ghost' (Soundridemusic) to the 80 s trailer timeline. (~1362 tok)
- `props3d.py` — Low-poly trailer props built from engine3d boxes/prisms (y up, metres). (~4399 tok)
- `render.py` — Render the cinematic trailer. (~1426 tok)
- `sfx.py` — Synthesised sound design for the cinematic trailer, laid onto the (~3027 tok)
- `shots.py` — The trailer's shots. Each Shot covers [start, end) on the trailer clock (~17692 tok)
- `thumbnail.py` — YouTube thumbnails (1280x720) composed from real trailer frames. (~1880 tok)
- `timeline.json` (~762 tok)
- `vertical.py` — 9:16 TikTok / YouTube Shorts / Reels cut of the cinematic trailer. (~2442 tok)
- `vo_mix.py` — Place the trailer narration on the 80 s music cut and mix it. (~2450 tok)

## tools/trailer_rpe6/

- `render.py` — RPE6 engine trailer for Call of Acaristan: the engine and the game, no story. (~12120 tok)
- `score.py` — Sound for the RPE6 trailer: "Shell Ghost" (Soundridemusic), placed so its (~1616 tok)
- `shorts.py` — Vertical 1080x1920 cuts of the RPE6 trailer for TikTok / YouTube Shorts. (~7130 tok)

## validation/

- `compileall.txt` (~9 tok)
- `M5_harbour_graphics.md` — Validation — M5 Harbour Graphics (~1012 tok)
- `multiplayer_ui.txt` (~92 tok)
- `smoke_test_initial_environment_failure.txt` (~1730 tok)
- `smoke_test.txt` (~2359 tok)
- `sprite_inventory.md` — Sprite inventory (Polish Task 7) (~1689 tok)
- `tcp_tunnel.txt` (~26 tok)
- `voice_audit_xlsx.csv` (~4068 tok)
- `voice_audit.csv` (~18252 tok)
- `voice_audit.md` — Voice-line audit (~24008 tok)
