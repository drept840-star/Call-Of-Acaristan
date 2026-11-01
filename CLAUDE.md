# OpenWolf

This project uses OpenWolf for context management. The always-on rules live in `.claude/rules/openwolf.md`; the hooks handle bookkeeping (anatomy index, memory log, read tracking) automatically.

For the full operating protocol (session handoff, memory discipline, bug logging), load the `openwolf` skill, or read `.wolf/OPENWOLF.md`. Regenerate the session handoff with `/handoff`.

# Directory

Where things live. Working rules (facades, shared state, map contract, renderer, sprite pipeline, story canon) are in `AGENTS.md`; read the section you need before editing that area.

## Run and verify
- `acaristan.py` - launcher; adds `src/` to `sys.path` and imports `app`. Run from the repo root (assets and saves are CWD-relative).
- `src/app.py` - entry module; the game runs on import.
- `python tools/smoke_test.py` - the working gate for game changes (`SMOKE TEST: OK`), plus `python -m compileall -q src`.
- `python tools/ae_ci.py` - full engine gate (`AE CI: OK`). Some checks fail independently of current work: mission4_stage_transitions, mission4_cinematic_arrest, mission5_shadow_finale geometry, mission5_harbour_art choreography.

## src/
- `engine/` - RPE6 kernels: ai, anim, assets, collision, core, dialogue, input, level, lighting, render2d, render3d (`ae.set3d/1` data, no renderer), save, scene, settings, text, timeline, ui, world. Pure: never imports game code, no import-time side effects. Public API changes need `tools/ae_api_snapshot.py` + `tests/api/engine_api.json`. Boundary checked by `tools/check_boundaries.py`.
- `game/` - game side of the engine boundary. Adapters `render3d_bridge.py`, `input_adapter.py`, `save_adapter.py` are the intended boundary, not violations. `world/legacy.py` bridges `STATE` objects to `engine.world`.
  - `game/content/` - authored data: levels, dialogue, timelines, sets, strings, meshes, textures, grades, lighting3d, per-mission packs `m1`-`m5`. Legacy Python tables stay reachable via `ACA_*_SRC=legacy`; they are fallbacks, not dead code.
  - `game/art/m1`-`m5` - code-authored mission art. `src/art/m5` is a compatibility shim over `game/art/m5`; edit `game/art`.
- `engine3d/` - 3D renderer: `core.py` (software), `gl.py` (ModernGL), `rig.py`, `ik.py`, `textures.py`. Use `engine3d.Renderer(...)`.
- `missions/` - `m0` (enemy types), `m1`-`m6`, `arena.py` (multiplayer), `walking_sim.py`. Each mission package `__init__.py` is a re-export facade; load order = import order in it. Typical parts: `meta`, `maps`, `decor`, `world`, `flow`, `systems`, `draw`.
  - `missions/m6/` - Whiteout: yard (`yard3d`, `yard_brain`, `yard_dress`, `yard_hud`), `stealth`, `train3d` (last playable beat), `bloc3d/` (panel blocks, stacks, tower, Cyrillic neon), `hud3d`, `m6_audio`. The finale is cutscene-only.
  - `missions/m7/` - Fallow Ground (all 7 beats): `farmyard` (top-down chores and prep), `raid3d` + `raid_brain` + `raid_world` + `raid_hud` (playable 3D raid), `choice` (radio choice, writes `STATE.m8_route`), `flow`/`systems`/`draw`. Films live in `cutscenes/m7*`. Notes at the end of `docs/MISSION7_PLOT.md`.
  - Mission 8 is planned only (`docs/MISSION8_PLOT.md`).
- `cutscenes/` - 2D and 3D cutscene hosts per mission (`m3*`, `m4aftermath`, `m5*`, `m6films`, `m6world3d`, `m6fx3d`), shared `figure_kit.py` (cast look `SPECS`), `cast3d.py`, `post3d.py`, `weather3d.py`.
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

A code-only knowledge graph of `src/` lives in `src/graphify-out/` (`graph.json`, `GRAPH_REPORT.md`, `graph.html`). For architecture questions (who calls X, what depends on Y, how A connects to B), query it before grepping the tree:
- `graphify query "<question>" --graph src/graphify-out/graph.json`
- `graphify explain "<node>"`, `graphify path "<A>" "<B>"`, `graphify affected "<node>"`, `graphify god-nodes` (all take the same `--graph`).
- Skim `src/graphify-out/GRAPH_REPORT.md` for hubs and communities.
Use plain Grep/Read for exact strings and for editing. The graph can go stale after big edits: refresh with `graphify update src` (no LLM needed).

# Delegated work

Subagents are rare (weekly limit). Work inline with direct tools. Spawn a Haiku 5.5 `searcher`/`implementer` only when the user asks or for a big sweep that would flood context. No two-pass plan/implement subagent flow. The DeepSeek/OpenCode workers (`ds-worker.mjs`, `/delegate`) stay retired.
