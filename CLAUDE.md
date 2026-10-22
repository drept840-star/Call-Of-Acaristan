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
  - `missions/m6/` - Black Notebook: yard (`yard3d`, `yard_brain`, `yard_dress`, `yard_hud`), `stealth`, `train3d` (last playable beat), `bloc3d/` (panel blocks, stacks, tower, Cyrillic neon), `hud3d`, `m6_audio`. The finale is cutscene-only.
  - Missions 7 and 8 are planned only (`docs/MISSION7_PLOT.md`, `MISSION8_PLOT.md`).
- `cutscenes/` - 2D and 3D cutscene hosts per mission (`m3*`, `m4aftermath`, `m5*`, `m6films`, `m6world3d`, `m6fx3d`), shared `figure_kit.py` (cast look `SPECS`), `cast3d.py`, `post3d.py`, `weather3d.py`.
- `core/` - legacy runtime: `state.py` (`STATE`), `game_core.py`, `camera.py`, `mapbuilder.py` (dependency-free), `artpack.py` (sprite sheet access), `save_system.py`, `settings_store.py`, `lighting.py`, `dev_jumps.py`.
- `entities/` - player, `enemy_ai.py`, weapons, weapon rig, corpses, death anims.
- `ui/` - menus (`main.py`), `hud.py`, `radio.py` + `pixfont.py` (bitmap fonts), shop, multiplayer screens, mission failed.
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

# Delegated work

Send mechanical work (searches, gate runs, renders, sweeps) to subagents through the Agent tool. They run on Haiku 5.5 (`claude-haiku-5-5`, set by `CLAUDE_CODE_SUBAGENT_MODEL` in `.claude/settings.local.json`). Write each task as an exact, self-contained brief with the commands to run, and spot-check its claims (counts, pass/fail) before relying on them. Design and code stay on the main model. The DeepSeek worker (`ds-worker.mjs`) is retired for this project: it was unreliable.
