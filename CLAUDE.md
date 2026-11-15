# OpenWolf

This project uses OpenWolf for context management. The always-on rules live in `.claude/rules/openwolf.md`; the hooks handle bookkeeping (anatomy index, memory log, read tracking) automatically.

For the full operating protocol (session handoff, memory discipline, bug logging), load the `openwolf` skill, or read `.wolf/OPENWOLF.md`. Regenerate the session handoff with `/handoff`.

# Directory

Where things live. Working rules (facades, shared state, map contract, renderer, sprite pipeline, story canon) are in `AGENTS.md`; read the section you need before editing that area. For exact files per task, cross-module call chains, the weapon ID crosswalk and per-subsystem gates, see `docs/ARCHITECTURE_MAP.md`.

## Run and verify
- `acaristan.py` - launcher; adds `src/` to `sys.path` and imports `app`. Run from the repo root (assets and saves are CWD-relative).
- `src/app.py` - entry module; the game runs on import.
- `python tools/smoke_test.py` - the working gate for game changes (`SMOKE TEST: OK`), plus `python -m compileall -q src`.
- `python tools/ae_ci.py` - full engine gate (`AE CI: OK`). Some checks fail independently of current work: mission4_stage_transitions, mission4_cinematic_arrest, mission5_shadow_finale geometry, mission5_harbour_art choreography.

## src/
- `engine/` - RPE6 kernels: ai, anim, assets, collision, core, dialogue, input, level, lighting, render2d, render3d (`ae.set3d/1` data, no renderer), save, scene, settings, text, timeline, ui, world. Pure: never imports game code, no import-time side effects. Public API changes need `tools/ae_api_snapshot.py` + `tests/api/engine_api.json`. Boundary checked by `tools/check_boundaries.py`.
- `game/` - game side of the engine boundary. Adapters `render3d_bridge.py`, `input_adapter.py`, `save_adapter.py` are the intended boundary, not violations. `world/legacy.py` bridges `STATE` objects to `engine.world`.
  - `game/topdown3d.py` - shared 2.5D top-down host (camera presets `CAMS` per mission, `View` projection and aim via `mouse_world`, cast/prop helpers). Used by the MP arena and M1 (`missions/m1/draw3d.py`). `ACA_TD_2D=1` forces the 2D top-down view; any renderer error falls back to 2D for the run.
  - `game/content/` - authored data: levels, dialogue, timelines, sets, strings, meshes, textures, grades, lighting3d, per-mission packs `m1`-`m5`. Legacy Python tables stay reachable via `ACA_*_SRC=legacy`; they are fallbacks, not dead code.
  - `game/art/m1`-`m5` - code-authored mission art. `src/art/m5` is a compatibility shim over `game/art/m5`; edit `game/art`.
- `engine3d/` - 3D renderer: `core.py` (software), `gl.py` (ModernGL), `rig.py`, `ik.py`, `textures.py`. Use `engine3d.Renderer(...)`.
- `missions/` - `m0` (enemy types), `m1`-`m6`, `arena.py` (multiplayer), `walking_sim.py`. Each mission package `__init__.py` is a re-export facade; load order = import order in it. Typical parts: `meta`, `maps`, `decor`, `world`, `flow`, `systems`, `draw`.
  - `missions/m6/` - Whiteout: `yard*` (yard3d/brain/dress/hud), `stealth`, `train3d` (last playable beat), `bloc3d/`, `hud3d`. Finale is cutscene-only.
  - `missions/m7/` - Fallow Ground: `farmyard` (top-down), `raid*` (playable 3D raid), `choice` (radio, writes `STATE.m8_route`). Films in `cutscenes/m7*`; notes in `docs/MISSION7_PLOT.md`.
  - `missions/m8/` - The Call; `STATE.m8_route` picks the ladder. `revenge/`: `trap*` (3D trap + gantry climb), `kill3d`, `chase3d`/`chase_set` (tractor chase), `epilogue3d`; films via `cutscenes/m8films.py` + `meta.M8_SCENES`, `beats` is the fallback. `duty/` reserved. Design: `docs/MISSION8_PLOT.md`.
- `cutscenes/` - 2D and 3D cutscene hosts per mission (`m3*`, `m4aftermath`, `m5*`, `m6films`, `m6world3d`, `m6fx3d`, `m8films`), `figure_kit.py` (deprecated re-export; cast look `SPECS` lives in `engine/anim/figure_kit.py`), `cast3d.py`, `post3d.py`, `weather3d.py`.
- `core/` - legacy runtime: `state.py` (`STATE`), `game_core.py`, `camera.py`, `mapbuilder.py` (dependency-free), `artpack.py` (sprite sheet access), `save_system.py`, `settings_store.py`, `lighting.py`, `dev_jumps.py`.
- `entities/` - player, `enemy_ai.py`, weapons, weapon rig, corpses, death anims.
- `ui/` - menus (`main.py`), `hud.py`, `radio.py` + `pixfont.py` (bitmap fonts), shop, multiplayer screens, mission failed. Multiplayer draws in 2.5D: `arena_view3d.py` (`make_view`, aim unprojection) over the 2D `arena_view.py`, cast and guns from `mp3d.py`; `ACA_MP_2D=1` forces 2D, and any 3D error falls back to 2D for the run.
- `audio/` - `audio.py`, `voice.py`, `voice_manifest.py` (`VO_xxx` rows, `KNOWN_MISSING_AUDIO`, `VOICE_ORDER`).
- `net/` - multiplayer: protocol, client, match, discovery, tunnel.
- `fx/` - 2D effects. `tools/` (under src) - dev-only input recorder and trailer bot.

## Outside src/
- `tools/` - CI gates (`ae_*.py`), smoke test, renders and shot scripts (`m5_*`, `m6_*`, `render_*`), multiplayer harnesses (`mp_*`), builds (`build_windows.py`, `ae_package.py`). `tools/sprites/` holds the sprite generators (`palette.py`, `kit.py`, one per family); rebuild with `tools/build_all_sprites.py`.
- `tests/` - `unit/` (pytest), `api/engine_api.json`, `golden/`, `replay/`, `loop/`, `data/`.
- `assets/` - `art/` (generated `spr_*.png` + `.json`), `3D`, `tex3d`, `sprites`, `fonts`, `music`, `voice`, `baked`.
- `docs/` - `LORE.md`, `MISSION*_PLOT.md`, `FIXES_STORIES.md` (deliberate re-reads; do not revert), `M6_HALOS_AND_ENDING_PLAN.md`, `worklog.md`. `docs/engine/` - `STATUS.md`, `ARCHITECTURE.md`, `ADAPTERS.md`, `BUGS.md`, `tutorial_add_mission.md`, `adr/`, `subsystems/`. Plans and reports are point-in-time; the shipped game wins on disagreement.
- `validation/` - gate outputs and audits (sprite inventory, voice audit).
- `.wolf/` - OpenWolf state: `STATUS.md` (handoff), `cerebrum.md`, `buglog.json`, `anatomy.md`.

Not project modules (skip them): `archive/`, `build/`, `dist/`, `previews/`, `shots/`, `_shots/`, `outputs/`, `handoff/`, `crash_reports/`, `trailers/`, `.venv/`, `.qoder/`, `.opencode/`, `.workbuddy-ai/`, `SKILLS/`, and the zips, logs (`*.log`, `*.err`) and scratch scripts at the root.

# Code graph (graphify)

For architecture questions (who calls X, what depends on Y), query `graphify query "<q>" --graph src/graphify-out/graph.json` (also `explain`, `path`, `affected`, `god-nodes`) before grepping; hubs in `src/graphify-out/GRAPH_REPORT.md`. Grep/Read for exact strings. Refresh after big edits: `graphify update src`.

Subagents: see the global rule. Spawn type is Haiku 5.5 `searcher`/`implementer`. The DeepSeek/OpenCode workers (`ds-worker.mjs`, `/delegate`) stay retired.
