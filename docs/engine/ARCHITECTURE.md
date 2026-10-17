# Retardovici Pulse Engine 6 Gold — Architecture

The engine is the `src/engine/` tree: 82 modules in 16 kernel packages,
extracted from the game strangler-style across Phases 1–9 (2026-10).
The game (`src/` everything else) is the engine's first and only
client. `ENGINE_NAME = "Retardovici Pulse Engine 6 Gold"`, version in
`engine.__version__`.

## The one rule that holds the shape

`src/engine/` never imports game code. Game code imports the engine
only through the public facades (`engine.<pkg>` with explicit
`__all__`) — rule E4, enforced by `tools/check_boundaries.py` together
with the W1 shared→mission import ratchet (baseline 49 since Phase
10 added Mission 0's one mission edge).

```
src/
  engine/            kernels (pure: no game imports, no import-time side effects)
    core/            app loop, clock, events, rng streams, services, settings schema
    scene/           Scene / SceneStack / CutsceneScene / InspectScene
    world/           ECS-lite: components, systems scheduler, prefabs
    render2d/        layers, drawables, render queue, camera, pens, postfx, static layers
    render3d/        ae.set3d/1 scene data (meshes are built by the host engine3d package)
    lighting/        light buffer + lightmap compositing
    text/            string table, fonts/glyphs, layout
    ui/              Theme + std widgets (one module per widget)
    anim/            figure kit + pose cache
    assets/          manifest, registry, bake/layerbake, loaders, watcher
    level/           ae.level/1 model + Tiled import
    dialogue/        ae.dialogue model + DialogueRunner (host protocol)
    timeline/        ae.timeline/1 model, expr language, TimelinePlayer
    settings/        typed layered settings kernel (defaults < file < env < CLI)
    save/            ae.save/1 snapshots + statehash (floats quantised 1e-4)
    input/           ActionMap (identity defaults; remapping at the app boundary)
  game/              facades over the kernels for game data (content loaders,
                     devtools), art packs, strings
  missions/          m0..m5 + walking_sim hosts (game code, engine clients)
  cutscenes/         shot renderers (registered takes), 3D scene hosts
  core/, ui/, ...    the legacy game runtime the hosts live in
  engine3d/          the 3D renderer package (GL + software fallback) the
                     render3d bridge feeds
tools/               ae_* gates: golden, loop, replay, bench, validate,
                     mission0, engine3d parity, package, ci
tests/               unit tests + API snapshot + oracle sets (golden/loop/replay)
```

## Data, not code (Phases 7–8)

Mission content lives as validated data under `src/game/content/`:
levels (`ae.level/1`), dialogues (`ae.dialogue`), timelines
(`ae.timeline/1`, shots + timed events), 3D sets (`ae.set3d/1`),
strings (`content/strings`). Loaders in `src/game/` keep per-id
caches; legacy Python tables remain reachable via `ACA_*_SRC=legacy`
env switches. `tools/ae_validate.py` loads every file through its
public loader in CI.

## Determinism

Named seeded RNG streams (`engine.core.RngStreams`), a fixed-step
clock, snapshot save (`engine.save`) whose `statehash` quantises
floats to 1e-4, and three oracle harnesses — golden frames
(`tools/ae_golden.py`), main-loop parity (`tools/ae_loop.py`),
input-stream replay (`tools/ae_replay.py`, one segment per mission;
`tools/ae_replay_check.py` proves save snapshots reproduce them).
Owner oracle sets live in `tests/`; sandbox sets are scratch
(recaptured per gate, slimmed after).

## Adding a mission

`docs/engine/tutorial_add_mission.md` + `tools/ae_new_mission.py`.
Mission 0 was built by following the tutorial literally and is the
standing proof (`tools/ae_mission0_check.py`) that a complete
mission — level, dialogue, timeline cutscene with a 3D set and an
inspect shot, two enemy types, HUD widgets — needs zero edits under
`src/engine/`.

## Where the details live

- `docs/engine/subsystems/*.md` — one page per kernel package.
- `docs/engine/adr/` — architecture decisions (ADR-001…021).
- `docs/engine/reports/phase*.md` — per-phase exit reports with the
  D1–D12 evidence tables.
- `docs/engine/BUGS.md`, `CHANGELOG.md`, `ADAPTERS.md` (A-001…A-013:
  every place game code adapts to a kernel boundary).
- `docs/engine/STATUS.md` — current state; `docs/worklog.md` — the
  changed-files log (this tree has no git).
