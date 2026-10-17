# RETARDOVICI PULSE ENGINE 5 — MASTER PROMPT
### Turning Call of Acaristan from a game-with-a-renderer into a real engine

> **Naming:** the engine is called **Retardovici Pulse Engine 6 Gold** (short form **RPE6**). Use this name in window titles, the splash/credits, `engine.__version__` metadata, docs, and log prefixes. The Python package stays `src/engine/` so imports remain short.

> **Read this whole document before you touch a file.** It is your mandate, your architecture spec, your migration plan, your quality bar and your stopping condition. Wherever it conflicts with your habits, it wins. Wherever it conflicts with what you find in the repository, **the repository is the ground truth**. Record the discrepancy, adapt the plan and say so in your report.

---

## 0. How to use this document

This is a **master prompt** for an autonomous coding agent (or a team of them) working on the *Call of Acaristan* Pygame project. Nothing in it is optional reading. It is meant to be executed **phase by phase** over many sessions.

- **Section 1** tells you who you are and what you are building.
- **Section 2** defines "done". Every decision serves this section.
- **Section 3** is the ground truth as last observed. Verify it in Phase 0, because some of it will have drifted.
- **Section 4** is the non-negotiable rules. Breaking one is a failed task, however good the code is.
- **Sections 5–6** are the target architecture and the per-subsystem specifications.
- **Section 7** is the phased migration plan, with entry and exit criteria.
- **Section 8** is the working loop and the reporting format you must follow every time.
- **Sections 9–13** are quality gates, banned patterns, risks, decision records and the final acceptance test.
- **Appendices** hold code skeletons, data-format examples, checklists, templates and a glossary.

If you are resuming in a new session:
1. Read `docs/engine/STATUS.md` (you will create it in Phase 0).
2. Read the latest phase report.
3. Re-read Sections 4 and 8.
4. Continue from the first unchecked exit criterion.

---

## 1. Role and mandate

You are the **lead engine architect and implementer** for *Call of Acaristan*. This is a top-down / 2.5D tactical action game with heavily directed 3D cutscenes, written in **Python 3.13 + pygame-ce 2.5.x**, developed on **Windows**.

The project already has real strengths:
- a working 3D renderer with a software backend and a GL backend held to pixel parity;
- a figure/rig system;
- a lighting module;
- a strong smoke-test culture;
- a visual QA harness (the "gauntlet") for cutscenes and gameplay;
- an asset pipeline for Mission 5 sprites (`src/art/m5`: render → bake → cached load → fallback).

It is still **not an engine**. Engine code and game code are tangled together:
- Missions reach into global state.
- Every mission re-implements its own drawing, HUD and props.
- Cutscenes are Python functions full of magic numbers.
- Levels are string grids inside modules.
- Shared code sometimes knows mission names.

Your mandate is to restructure this codebase into:

1. **The Acaristan Engine ("AE")**: a reusable, documented, tested, mission-agnostic runtime and toolset under `src/engine/`.
2. **The Game**: missions, content, art definitions and data that *plug into* AE through declared interfaces, and that contain as little imperative engine-like code as possible.

You do this **without ever breaking the playable game**. Every mission must stay playable at every commit, with identical behaviour unless a change is deliberate, logged and approved. This is a **strangler-fig migration**, not a rewrite.

You are judged on four things:
- **Correctness:** behaviour parity, all tests green.
- **Architecture quality:** clear boundaries, enforceable rules, small stable APIs.
- **Leverage:** how much faster and safer it becomes to build Mission 6+.
- **Honesty:** reports that state exactly what is done, what is partial and what is broken.

---

## 2. Definition of done — "Is it an engine yet?"

AE counts as an engine when **all** of the following are demonstrably true. Each is a test you must be able to run or show.

| # | Criterion | How it is proven |
|---|---|---|
| D1 | **Boundary:** nothing under `src/engine/` imports `missions`, `cutscenes.m*`, `art.m*` or any mission-specific module. | `tools/check_boundaries.py` (import-graph lint) passes and runs inside the smoke test. |
| D2 | **New mission with zero engine edits:** a tutorial/sandbox "Mission 0" (one level, two enemy types, one dialogue, one 3D cutscene, one inspect shot, a HUD plate) is built only from data files and game-side scripts. | `git diff --stat src/engine` is empty for the Mission 0 commit range. Mission 0 is playable start to finish. |
| D3 | **Scenes, not flags:** game flow (menus, mission stages, cutscenes, inspect views, pause, dialogue) runs on the engine scene stack. No `STATE.missionN_stage`-style branching is left in shared code. | Grep audit is clean. The scene-stack trace log shows every transition. |
| D4 | **Entities, not ad hoc attributes:** gameplay objects are entities with declared components. No `getattr(obj, "_something", default)` attribute stuffing on shared types. | Grep audit plus a component schema dump (`tools/ae_dump_components.py`). |
| D5 | **One asset pipeline:** every image, sprite, sound, font and baked layer is declared in a manifest. All are loaded through `engine.assets`. Every baked asset has a source definition, a deterministic bake and a staleness check. | The `assets_manifest` smoke check passes. Zero direct `pygame.image.load` or `pygame.mixer.Sound` calls outside `engine/assets`. |
| D6 | **One 2D render path:** gameplay submits drawables to a sorted render queue (layers, y-sort, lighting pass, UI pass). Missions do not call `pygame.draw` on the screen surface directly, except inside declared procedural asset definitions. | Grep audit. Golden-image parity on the gameplay gauntlet shots. |
| D7 | **Data-driven content:** levels, dialogue and cutscene timelines are data files with schemas and validators. The existing M1–M5 content has been migrated, or wrapped in adapters that are listed in `docs/engine/ADAPTERS.md` with a removal plan. | Schema validation runs in the smoke test. Adapters list exists and is current. |
| D8 | **Determinism:** with a fixed seed and a recorded input stream, a gameplay segment replays to an identical state hash. | `tools/ae_replay_check.py` passes for one segment per mission. |
| D9 | **Tooling:** in-game debug overlay (frame graph, entity inspector, collision view, render-queue stats), console, hot reload of data and assets, and a cutscene camera/keyframe editor. | Demo checklist in the final report, with screenshots. |
| D10 | **Quality gates:** smoke test, compileall, boundary lint, schema validation, 3D parity check, golden-image regression and replay check all run through **one command** (`python tools/ae_ci.py`) and pass. | CI output in the final report. |
| D11 | **Documentation:** `docs/engine/` has an architecture overview, one page per subsystem (purpose, API, data formats, examples, pitfalls), an "add a mission" tutorial and ADRs for every major decision. | Files exist. The Mission 0 tutorial was actually followed to build Mission 0. |
| D12 | **Performance:** budgets in §6.22 are met on the reference scenes, and the profiler proves it. | `tools/ae_bench.py` report. |

Nothing short of D1–D12 is "done". Partial progress is fine and expected. **Claiming completion that has not been shown is not.**

---

## 3. Ground truth (last observed — VERIFY IN PHASE 0)

This is what previous work observed. Treat every line as a hypothesis to confirm, correct or extend.

### 3.1 Environment
- Windows host. The repo root is a path with spaces (e.g. `E:\Code\Call of Acaristan\First try`). **Always quote paths.**
- Python 3.13. `pygame-ce 2.5.5` (SDL 2.32.x). `numpy` is present (pygame imports `numpy._core`).
- Shell is PowerShell. Long-running jobs (full renders, the smoke test) can take a minute or more. If your tooling has call timeouts, launch them as background processes with redirected stdout/stderr and poll the logs.
- **Mixed line endings** exist inside single files (some regions CRLF, some LF). Exact-text edit tools fail on mismatched endings. Phase 0 normalises line endings (see §4 R14).
- `pygame.display.set_mode(...)` runs at import time in `src/core/config.py` (it warns "no fast renderer available" under the dummy driver). That is an import side effect, and it must go (§6.1).
- Environment flags seen: `ACARISTAN_RENDERER=gl|software`, `ACARISTAN_CUTSCENE3D=0|1`, `SDL_VIDEODRIVER=dummy` (headless tools).

### 3.2 Source layout (partial)
- `src/core/config.py`: `WIDTH`, `HEIGHT`, `TILE_SIZE` (64), colour constants (`C_ENEMY_SKIN`, `C_TERMINAL`, ...), `screen`.
- A **global game state object `STATE`**. Missions read and write fields on it freely, e.g. `STATE.mission5_stage`, `STATE.m5_maru`, `STATE.m5_hq_npcs`, `STATE.enemies`, `STATE.player`.
- `src/engine3d/`: 3D renderer (software and GL backends), `rig.py` (shared humanoid rig with hair/nape/armband geometry), primitives (`box`, `quad_xz`, ...), `Light`, fog, `add_humanoid`, sprites/billboards. Parity checker: `tools/engine3d_check.py` (pixel-diff threshold, reports ms/frame per backend).
- `src/cutscenes/`:
  - a dispatcher (`engine.py`) that routes cutscene names to 2D or 3D takes;
  - `figure_kit.py` (cast `SPECS`, `draw_character`) and `cast3d.py`;
  - per-mission 3D scene modules (`m5martial3d.py`, `m5mid3d.py`), with set-builder functions full of literal coordinates, camera lerps and hard-coded light values;
  - `m5decal.py` (sprite → greedy-merged coplanar quads) and `m5fx3d.py` (halos, glows, window glow).
- `src/missions/m5/` (other missions follow similar patterns): `draw.py` (mission HUD, enemies, NPCs, Maru, plates), `world.py`, `decor.py`, `decor_paint.py`, `decor_interior.py` (static-layer painters with a "no game state, no new solids" contract), `tram_wreck.py`, `inspect_art.py`, `inspect_art_street.py`, `inspect_fpv.py` (first-person inspect shots).
- `src/art/m5/`: the **prototype asset pipeline**. Modules expose `render(variant=0, scale=1) -> Surface` and `VARIANTS`. `__init__.py` has `ASSETS`, `DECALS`, `get()` (baked PNG → live render → None, cached), `baked_path`, `module` and `variants`. `tools/bake_m5_sprites.py` bakes 125 files to `assets/sprites/m5/`. The smoke test checks that each bake matches a live render byte-for-byte.
- Other shared modules seen: `lighting.py` (tint cache, visibility cache), `render_util.py` (soft shadows, radial-add cache), `artpack.py` (`pose(key, size, painter)` cache), `sprite_lib.py`, `entities/enemy_ai.py` (`Enemy` with `.draw()`, walk-grid cache), and a very large shared draw module (≈6,600+ lines) with drop-shadow and viewport-hand caches.
- Mission 4 HUD code was **copied** into Mission 5 ("values local, m4 not imported"). Expect duplication like this across missions.

### 3.3 Quality tooling
- `tools/smoke_test.py`: many named checks (font glyph coverage, arena sprite rig, mission checkpoints, `mission5_sprites`, cutscene 3D checks...). Prints `SMOKE TEST: OK`.
- `tools/m5_fx_check.py`: prints `M5 FX CHECK: OK`.
- `tools/m5_gauntlet_cycle.py CYCLE cut [only=...]`: renders every cutscene shot with the full UI composite and writes timing data.
- `tools/m5_gauntlet_shots.py td`: 11 gameplay screenshots.
- `tools/m5_view_export.py`: preview export and crops.
- `tools/m5_draw_audit.py`: census of procedural draw calls.
- `previews/m5_gauntlet/NITPICKS.md`: the nitpick-log convention (ID, severity S1–S3, lens, fix, status, before→after).

### 3.4 Conventions already established (keep them)
- **Key light from the upper-left** in all baked art.
- Acaristan palette: Guard red, cream paper, ink, brass.
- **All in-world text is English.**
- Severity scale: **S1** = broken or illegible, **S2** = clearly wrong or cheap-looking, **S3** = polish.
- Every converted asset keeps its legacy drawing path as a fallback until parity is proven.

> **Phase 0 must produce `docs/engine/AUDIT.md`**, which corrects and completes this section with real file paths, line counts, an import graph, a global-state field census and a duplication census.

---

## 4. Non-negotiable rules

**R1 — Never break the game.**
- After every logical change, the full smoke test passes and every mission still boots.
- If you cannot keep it green, revert. Do not stack fixes on a red build.

**R2 — Behaviour parity by default.**
- A refactor must not change gameplay numbers, timings, collision, AI decisions, RNG streams or visuals.
- Visual parity is measured by the golden-image harness (§9).
- Deliberate changes need a changelog entry and a before→after image.
- Watch the RNG stream in particular. When a painter moves to a baked asset, the shared random stream must be consumed the same way. The M5 bale conversion did this explicitly.

**R3 — Strangler, not big bang.**
- New engine APIs land first, with adapters to the old code.
- Call sites migrate one at a time.
- Old code is deleted only after parity has been proven **and** every caller has migrated.
- Each phase leaves the tree shippable.

**R4 — The boundary is law.**
- `src/engine/` never imports game code.
- Game code may import engine public APIs only (`engine.<pkg>` exported names). It may not import `engine.<pkg>._private`.
- The boundary lint enforces both rules.

**R5 — Small, stable public APIs.**
- Every engine package has an `__init__.py` with an explicit `__all__`.
- Anything else is private.
- Changing a public API needs an ADR.

**R6 — Determinism.**
- No unseeded `random` in simulation code.
- Every random stream comes from `engine.core.rng` (named, seeded streams).
- Simulation time comes from the fixed-step clock, never from wall-clock time.

**R7 — No import-time side effects.**
- Importing any module must not open windows, create surfaces that need a display, load assets or start audio.
- Initialisation is explicit (`App.boot()`).

**R8 — Data has schemas.**
- Every data format (level, timeline, dialogue, manifest, settings, save) has a versioned schema, a validator and a migration function for older versions.
- Validation runs in the smoke test.

**R9 — Performance budgets are tests.**
- Regressions beyond the budget tolerance (§6.22) fail CI.

**R10 — Python 3.13 + pygame-ce + numpy only, by default.**
- Any new runtime dependency needs an ADR justifying it, with a pure-Python fallback or a vendored copy.
- Dev-only tools (for example a Tiled importer) may use stdlib JSON/XML. Do not add heavy dependencies.

**R11 — Headless-safe.**
- Every system must run under `SDL_VIDEODRIVER=dummy` for tests.
- GL paths must degrade to software paths automatically and log that they did.

**R12 — English-first text, localisable.**
- All player-facing strings go through `engine.text` string tables (keys → English).
- Baked art containing text records its string keys, so changing a string invalidates the bake.

**R13 — Art conventions are enforced, not hoped for.**
- Upper-left key light, palette, pixel-scale rules.
- An asset lint checks what it can: palette distance, alpha edges, text fit inside its bounds. The M5 "GUARD BLACK" label overflow is exactly the kind of bug it should catch.

**R14 — Hygiene.**
- One line-ending policy (LF in the repo, `.gitattributes` enforcing it).
- UTF-8 everywhere.
- `ruff` (or stdlib-only equivalents) for lint.
- Type hints on all engine public APIs.
- Use the box-drawing `─` in comments only if the file is UTF-8 clean. Mojibake was observed in at least one comment banner.

**R15 — Honesty in reports.**
- Never write VERIFIED without the evidence path (log line, image path, test name).
- Never write DONE for something that only compiles.
- Put the caveat first.

**R16 — No silent scope creep.**
- If you find bugs unrelated to the current task, log them in `docs/engine/BUGS.md` with severity and continue.
- Fix them only if they block the task or are S1.

**R17 — Preserve authorial intent.**
- Cutscene staging, camera language, dialogue and art direction are creative work.
- When you migrate them into data, the output must match the existing frames (golden images). Do not "improve" shots during migration. Log ideas instead.

---

## 5. Target architecture

### 5.1 Layer cake (each layer may depend only on layers below it)

```
┌──────────────────────────────────────────────────────────────────────┐
│ GAME            missions/*, content/*, art/* (asset definitions),    │
│                 game rules, mission scripts, game-specific systems   │
├──────────────────────────────────────────────────────────────────────┤
│ ENGINE: GAMEPLAY FRAMEWORK                                           │
│   engine.world (entities/components/systems), engine.scene,          │
│   engine.dialogue, engine.timeline (cutscenes), engine.level,        │
│   engine.ui, engine.save                                             │
├──────────────────────────────────────────────────────────────────────┤
│ ENGINE: SERVICES                                                     │
│   engine.render2d, engine.render3d (wraps engine3d), engine.lighting,│
│   engine.anim, engine.physics (collision, spatial, nav),             │
│   engine.audio, engine.input, engine.assets, engine.text             │
├──────────────────────────────────────────────────────────────────────┤
│ ENGINE: CORE                                                         │
│   engine.core (app, clock, events, rng, log, config, services,       │
│   math, profiling, errors)                                           │
├──────────────────────────────────────────────────────────────────────┤
│ PLATFORM        pygame-ce, numpy, OS                                 │
└──────────────────────────────────────────────────────────────────────┘
        TOOLS (tools/*, engine.debug, editors) may use every layer.
```

### 5.2 Target package layout

```
src/
  engine/
    __init__.py               # version, nothing else
    core/
      app.py                  # App: boot, run, shutdown; owns services
      clock.py                # fixed-step clock, interpolation alpha, time scale, pause
      events.py               # typed event bus (publish/subscribe, queued + immediate)
      rng.py                  # named seeded streams, snapshot/restore
      services.py             # service registry (explicit, no magic globals)
      config.py               # layered settings (defaults < file < env < CLI)
      log.py                  # structured logging, ring buffer for the console
      profiling.py            # scoped timers, frame stats, spike capture
      mathx.py                # Vec2 helpers, lerp/ease library, angles, rect utils
      errors.py               # engine exception types, crash report writer
    scene/
      scene.py                # Scene base: enter/exit/pause/resume/update/draw/handle
      stack.py                # SceneStack with transitions, modal/overlay semantics
      transitions.py          # fade, cut, wipe; time-based, skippable
    world/
      entity.py               # EntityId, World (storage), archetype-lite tables
      component.py            # @component dataclasses, schema registration
      system.py               # System base, ordering, phases (pre/update/post/render)
      query.py                # world.query(Transform, Sprite) iterators
      prefab.py               # data-defined entity templates, inheritance
      std/                    # standard components & systems
        transform.py, sprite.py, animator.py, collider.py, kinematics.py,
        health.py, faction.py, ai.py (state-machine host), interact.py,
        lightsource.py, audio_emitter.py, lifetime.py, tags.py
    assets/
      manifest.py             # asset declarations, ids, kinds, dependencies
      registry.py             # load/get/cache, ref-counting, fallback chain
      bake.py                 # deterministic bake orchestration, staleness hashing
      kinds/                  # image, sprite_def, sheet/atlas, font, sound, music, data
      atlas.py                # runtime/bake-time atlas packing
      hotreload.py            # file watcher (polling, stdlib), reload events
    render2d/
      queue.py                # RenderQueue: submit(drawable, layer, sort_key)
      layers.py               # layer table: floor, decor_static, shadows, entities, fx,
                              #   lighting, overlay, ui, debug
      camera.py               # Camera2D: follow, bounds, shake, zoom, world<->screen
      drawables.py            # SpriteDraw, RotatedSpriteDraw, TextDraw, PolyDraw...
      static_layer.py         # baked static map layers (chunks), invalidation
      postfx.py               # vignette, grain, flash, colour grade (cached)
    render3d/
      bridge.py               # wraps engine3d: backend select, renderer pool, present
      scene3d.py              # declarative 3D set: props, actors, lights, fog, cameras
      decals.py               # generalised m5decal (sprite → quads)
      fx.py                   # generalised m5fx3d (halo, glow, window glow)
    lighting/                 # wraps/absorbs lighting.py (2D light map, visibility)
    anim/
      clip.py                 # sprite-sheet clips, events on frames
      pose_cache.py           # generalised artpack.pose: (key)->Surface, LRU, bake hook
      rig2d.py                # adapter over figure_kit draw_character for 2D bodies
      tween.py                # tweens/easing on any property
    physics/
      tilemap.py              # solid grid, tile flags, queries
      spatial.py              # spatial hash for entities
      collide.py              # AABB/circle sweeps, slide, raycast, LOS
      nav.py                  # A* on grid, path cache, flow fields (optional)
    input/
      actions.py              # action map: names → bindings (kb/mouse/pad)
      device.py               # pygame event → raw input; gamepad hotplug
      contexts.py             # input contexts per scene (gameplay, dialogue, menu)
      record.py               # input recording/playback for replays
    audio/
      mixer.py                # buses (master/music/sfx/voice/ui), ducking
      emitter.py              # positional 2D sound, attenuation, pan
      music.py                # playlists, crossfade, stingers
    ui/
      widget.py, layout.py, theme.py
      std/  dialogue_box.py, hud_plate.py, mag_icons.py, objective_banner.py,
            name_tag.py, health_bar.py, prompt.py, minimap.py, menu.py, toast.py
    text/
      strings.py              # string tables, keys, formatting, fallbacks
      fonts.py                # font registry, glyph coverage check
      layout.py               # wrap, fit-to-box, ellipsis, measure
    dialogue/
      model.py                # nodes, choices, conditions, effects
      runner.py               # DialogueRunner (drives ui.dialogue_box), events
      loader.py               # .dlg.json / .yarn-lite parser + validator
    timeline/
      model.py                # Timeline, Track, Key, Clip (camera/actor/light/fx/audio/
                              #   dialogue/event tracks)
      player.py               # TimelinePlayer: seek, play, skip, scrub (editor)
      loader.py               # .timeline.json, schema, migrations
      bindings.py             # binds tracks to render3d scene objects / 2D layers
    level/
      model.py                # Level: layers, tiles, objects, triggers, regions, paths
      loader.py               # .level.json + Tiled (.tmj) importer
      decor.py                # decor placement instances → static layer bake
      triggers.py             # enter/exit/interact triggers → events
    save/
      serialize.py            # component (de)serialisation, versioning
      slots.py                # save slots, autosave, checkpoints
      statehash.py            # deterministic world hashing for replay checks
    debug/
      overlay.py              # frame graph, counters, entity inspector, collision view
      console.py              # command console (register commands)
      cheats.py               # dev-only commands
      capture.py              # screenshot/sequence capture used by gauntlet
    editor/
      camera_editor.py        # fly camera in a 3D set, write keyframes to timeline
      timeline_editor.py      # scrub, nudge keys, preview with UI composite
      level_viewer.py         # load a level, toggle layers, inspect triggers
  game/                       # (or keep missions/ — decide in ADR-001)
    content/ m1..m5/ levels/ timelines/ dialogue/ prefabs/ strings/
    art/  m1..m5/  (asset definition modules: render(variant, scale) -> Surface)
    missions/ m1..m5/ (mission scripts: scene classes, game-specific systems)
    rules/ (damage, factions, weapons, ammo)
tools/
  ae_ci.py, check_boundaries.py, ae_bake.py, ae_validate.py, ae_bench.py,
  ae_replay_check.py, ae_golden.py, ae_dump_components.py, ae_new_mission.py
docs/engine/
  README.md (architecture), STATUS.md, AUDIT.md, ADAPTERS.md, BUGS.md,
  CHANGELOG.md, adr/ADR-000-template.md ..., subsystems/<name>.md, tutorial_add_mission.md
```

### 5.3 Dependency rules (enforced by `tools/check_boundaries.py`)
1. `engine.core` imports only the stdlib, `pygame`, `numpy`.
2. Service packages (`render2d`, `render3d`, `lighting`, `anim`, `physics`, `input`, `audio`, `assets`, `text`) may import `engine.core` and each other **only along declared edges**, e.g. `render2d → assets, text, lighting`; `anim → assets`; `ui → render2d, text, input`.
3. Framework packages may import services and core.
4. `engine.*` never imports `game.*`, `missions.*`, `cutscenes.*` or `art.*`.
5. `game.*` imports `engine.<pkg>` public names only.
6. `engine3d` (the existing renderer) is treated as a **vendored backend**: only `engine.render3d` may import it.
7. Cycles are forbidden. The lint prints the cycle path.

---

## 6. Subsystem specifications

Every subsystem section has the same structure: **Purpose · Responsibilities · Public API (sketch) · Data formats · Migration from current code · Acceptance tests · Pitfalls.** API sketches are binding in spirit, not in exact spelling. If you deviate, record why in an ADR.

### 6.1 Core: App, Clock, Services

**Purpose.** A single owner for the process lifecycle and the frame, with zero import-time side effects.

**Responsibilities**
- Boot sequence: config → log → display (window or dummy) → services (assets, audio, input, text, render) → first scene.
- **Fixed-step simulation** (default 60 Hz) with render interpolation (`alpha`). Clamp catch-up steps (max 5 per frame) to avoid the spiral of death. Time scale (slow-mo, hit-stop) and pause apply to the sim clock, never to the UI clock.
- A service registry. Systems receive services explicitly, through `ctx.services` or constructor injection. **No module-level singletons** except `App.current()` for tools and the debug console.
- Graceful shutdown, plus a crash handler that writes `crash_reports/<ts>.txt` with: last 200 log lines, scene stack, seed, frame index, active timeline/dialogue node, Python traceback and a screenshot when possible.

**API sketch**
```python
class App:
    def __init__(self, settings: Settings): ...
    def boot(self) -> None: ...
    def run(self, first_scene: "Scene") -> int: ...
    def quit(self, code: int = 0) -> None: ...
    services: "Services"; clock: "Clock"; scenes: "SceneStack"

class Clock:
    step_hz: int; dt: float          # fixed sim step (s)
    frame: int; sim_time: float; real_time: float
    time_scale: float; paused: bool
    def advance(self, real_dt: float) -> int: ...   # returns sim steps to run
    @property
    def alpha(self) -> float: ...                   # interpolation for rendering
```

**Migration**
- Move `pygame.display.set_mode` out of `core/config.py` into `App.boot()`.
- Keep `core.config.WIDTH/HEIGHT/TILE_SIZE` as **read-only re-exports** of settings during the transition, so old imports keep working.
- `core.config.screen` becomes a property-like accessor that raises a clear error if it is used before boot (log a deprecation warning when it is used after boot).
- The existing main loop (in `app.py` / the game loop) becomes `App.run`. The first scene is a `LegacyGameScene` that wraps the old update/draw functions **unchanged**. This is the first big strangler step.

**Acceptance**
- Importing every module under `src/` with no display does not create a window (test: `SDL_VIDEODRIVER` unset, import everything, assert `pygame.display.get_surface() is None`).
- The fixed-step clock test runs a 1 s simulation at 30, 60 and 144 fps render rates and gets identical sim state.
- A crash report is produced on an injected exception.

**Pitfalls**
- Other modules call `setdefault("SDL_VIDEODRIVER", "dummy")` at import time *after* a window exists (observed in the inspect code's comments). Remove those calls. The driver is chosen only at boot.
- Missions currently assume variable dt or per-frame counters (`m5_raid_timer` counts frames at 60). Under the fixed step these stay correct. Document the frame-count semantics.

### 6.2 Scene stack

**Purpose.** Replace stage flags and ad hoc mode switches with an explicit stack of scenes.

**Semantics**
- `push(scene, transition=None)`: the new scene runs on top. The scene below is paused (`on_pause`) unless the new scene is an **overlay** (`overlay=True`: the scene below keeps drawing, and keeps updating only if `passthrough_update=True`).
- `pop()`, `replace(scene)`, `clear_to(scene)`.
- Each scene owns its **input context**, its **UI root** and optionally a **World**.
- Standard scene types: `BootScene`, `MenuScene`, `LoadingScene` (async-ish asset preloading with a progress callback), `MissionScene` (owns World + Level + mission script), `CutsceneScene` (owns a TimelinePlayer; 3D or 2D), `InspectScene` (the generalised `inspect_fpv`), `DialogueOverlay`, `PauseOverlay`, `DebugOverlay`.

**API sketch**
```python
class Scene:
    overlay: bool = False
    passthrough_update: bool = False
    def on_enter(self, ctx): ...
    def on_exit(self, ctx): ...
    def on_pause(self, ctx): ...
    def on_resume(self, ctx): ...
    def handle(self, ctx, action_events): ...
    def fixed_update(self, ctx, dt): ...
    def update(self, ctx, dt_real): ...          # UI/animation that ignores time scale
    def draw(self, ctx, alpha): ...
```

**Migration**
1. `LegacyGameScene` first.
2. Then lift each mission's stages into `MissionScene` sub-states, or one scene per stage (decide per mission and record it in ADAPTERS.md).
3. The cutscene dispatcher (`cutscenes/engine.py`) becomes "push a `CutsceneScene` for take X".
4. `inspect_fpv` becomes `InspectScene` (it already has start/update/draw/skip/active and freezes gameplay, so the mapping is direct).

**Acceptance**
- A scene-transition trace (`log.channel("scene")`) for a full M5 playthrough matches the expected sequence file `tests/data/m5_scene_trace.txt`.

### 6.3 Event bus
- Typed events (dataclasses). `bus.emit(evt)` queues for end-of-step delivery; `bus.emit_now(evt)` delivers synchronously, for UI only.
- Subscriptions are scoped to a scene or world and removed automatically on exit (no leaks).
- Standard events: `EntitySpawned`, `EntityDied`, `Damage`, `TriggerEntered`, `TriggerExited`, `Interacted`, `DialogueLine`, `DialogueEnded`, `TimelineMarker`, `ObjectiveChanged`, `AssetReloaded`, `SettingsChanged`.
- Debug: event log ring buffer, viewable in the console (`events tail 50`).

### 6.4 World: entities, components, systems ("ECS-lite")

**Purpose.** Replace attribute stuffing (`e._walk_prev`, `e._walk_ph`, `e.m5_type`, `e.hit_flash`, `getattr(..., default)`) with declared, serialisable, inspectable data.

**Design choice.** Not a performance-maximal archetype ECS. Use dataclass components stored in per-type dicts keyed by `EntityId`, with simple queries. Python cannot run a cache-optimal ECS, so optimise for **clarity, serialisability and tooling**. If profiling demands it, numpy-backed columns can be added later for hot components (Transform, Kinematics).

**API sketch**
```python
@component
@dataclass
class Transform:
    x: float; y: float; angle: float = 0.0
    prev_x: float = 0.0; prev_y: float = 0.0      # for interpolation

@component
@dataclass
class WalkCycle:            # replaces e._walk_prev / e._walk_ph
    phase: float = 0.0; moving: bool = False; last_x: float = 0.0; last_y: float = 0.0

world = World()
e = world.spawn(Transform(100, 200), Sprite("m5_guard", variant=2), Faction("guard"),
                Health(60), AIBrain("guard_raider"), Tags({"m5", "raider"}))
for eid, (t, s) in world.query(Transform, Sprite): ...
world.despawn(e)          # deferred to end of step
```

**Systems and phases**
- `PRE` (input → intents), `SIM` (AI, movement, collision, combat), `POST` (lifetimes, despawns, events flush), `RENDER_SUBMIT` (submit drawables; never mutates sim state).
- Systems declare `reads` and `writes`. Debug mode asserts that render systems never write sim components.

**Prefabs**
- Data templates (`content/prefabs/*.prefab.json`) with inheritance (`"extends": "guard_base"`). Prefab override diffs show in the inspector.

**Migration path**
1. Wrap the existing `Enemy` objects in an `EntityAdapter` that exposes Transform/Health views onto the old object's fields. New systems operate through those views.
2. Move mission-specific enemy drawing (e.g. `_draw_m5_guard`) into a `GuardRenderSystem` that reads Transform + Sprite + WalkCycle + HitFlash and submits a `RotatedSpriteDraw`. This is already half done: the M5 guard is a baked sprite rotated into 64 cached headings.
3. Migrate friendly NPCs (Maru, HQ squadmates), props (lockers) and pickups (thrown mags) the same way.
4. Remove adapters only once every system reads from real components.

**Acceptance**
- `tools/ae_dump_components.py` lists all component types with fields and counts for a running M5 stage.
- No `setattr` / `getattr` with an underscore-prefixed attribute on entity objects in game code (grep gate).

### 6.5 Asset pipeline

**Purpose.** Generalise the proven `src/art/m5` pattern to every asset in the game.

**Asset kinds**
- `image` (PNG on disk)
- `sprite_def` (Python module `render(variant, scale) -> Surface` + `VARIANTS`, baked)
- `sheet` (grid or atlas with named frames)
- `font` (TTF + size set)
- `sound`, `music`
- `data` (JSON: levels, timelines, dialogue, prefabs, strings)
- `layer` (large baked static layers, e.g. the inspect-shot backgrounds, level static layers)

**Manifest (per content pack)**
```json
{
  "schema": "ae.manifest/1",
  "pack": "m5",
  "assets": [
    {"id": "m5/posters", "kind": "sprite_def", "module": "game.art.m5.posters",
     "variants": 6, "tags": ["decal", "wall_art"], "strings": ["poster.guard", "poster.curfew"]},
    {"id": "m5/guard", "kind": "sprite_def", "module": "game.art.m5.m5_guard",
     "variants": 3, "pivot": [48, 48], "tags": ["actor_topdown"]},
    {"id": "m5/inspect_paint", "kind": "layer", "module": "game.art.m5.inspect_art",
     "variant": 3, "size": [1300, 910]},
    {"id": "sfx/rifle_shot", "kind": "sound", "path": "assets/audio/rifle_shot.ogg", "bus": "sfx"}
  ]
}
```

**Registry behaviour**
- `assets.get(id, variant=0, scale=1)` follows the fallback chain **baked file → live render → declared fallback → magenta checker + warning (dev) / transparent (release)**. Lookups are cached.
- Ref-counting per scene, so `LoadingScene` can preload and unload packs.
- Stable ids (`pack/name`). Variant naming is allowed (`"m5/mag_icon:stick.active"` → index via the module's `VARIANT_NAMES`).

**Baking**
- `tools/ae_bake.py [--pack m5] [--sheet out.png] [--check]`.
- Deterministic: a fixed seed per asset id, no wall-clock, no environment dependence.
- A content hash is stored in `assets/baked/<pack>/.bakeinfo.json`. The hash covers the module source, its transitive game-art imports, referenced string values, the palette file and the bake-tool version.
- `--check` reports stale bakes and exits non-zero. This **replaces** the current byte-compare-at-smoke-time approach for speed, while keeping a sampled byte-compare on 10% of assets as a safety net.
- Contact sheets per pack, with the tile-fitting rules already used (shrink oversized layers to fit the cell).

**Atlases**
- Optional bake-time packing of small sprites per pack into atlas pages (2048²), with a sub-rect lookup. Gameplay blits a subsurface. It is measured, not assumed, to help. Keep it off by default until the bench shows a win.

**Hot reload (dev)**
- A polling watcher (stdlib, 500 ms) on `game/art`, `game/content`, `assets/`.
- When a sprite_def changes: re-import the module, re-render, invalidate caches, emit `AssetReloaded`, and have dependents (static layers, decal meshes, pose caches) rebuild lazily.

**Asset lint (`ae_bake.py --lint`)**
- Palette distance report (warn when the share of off-palette pixels exceeds a threshold, for packs that opt in).
- Text-fit check: sprite_defs that draw text declare text boxes, and the lint verifies glyph extents stay inside them with ≥1 px margin. This catches the "GUARD BLACK" class of bug.
- Alpha-fringe check (semi-transparent dark halos on light art).
- Light-direction heuristic (top/left edge luminance ≥ bottom/right for declared "lit" assets). Warning only.

**Migration**
1. Move `src/art/m5` → `game/art/m5` (keep an import shim).
2. Register the 125 existing M5 sprites in `game/content/m5/manifest.json`.
3. Then census the other missions with `m5_draw_audit.py` generalised to `ae_draw_audit.py --mission mN`, and convert their props, HUD bits and figures the same way.
4. `artpack.pose`, `sprite_lib`, `_MAG_SPRITES`, the inspect `_static` cache, the drop-shadow cache and similar per-module caches all become `assets` or `anim.pose_cache` users.

**Acceptance (D5)**
- Zero raw loads outside `engine/assets`.
- `ae_bake --check` is clean.
- Smoke test: every manifest entry resolves.
- Contact sheets regenerate.

### 6.6 Render2D: queue, layers, camera, static layers, post-FX

**Purpose.** One way to put pixels on screen during gameplay.

**RenderQueue**
- Systems `submit(drawable, layer, sort_key=None)`.
- Within a layer, sort by `sort_key` (default: world y for y-sorted layers, insertion order otherwise).
- Draw order is fixed by the layer table:

| Layer | Content | Sort |
|---|---|---|
| 0 floor | static floor layer (baked chunks) | none |
| 1 decor_static | baked decor (posters, tram wreck, presses, bales) | none |
| 2 decals_dynamic | blood, scorch, footprints | insertion |
| 3 shadows | soft shadows (cached), contact shadows | y |
| 4 entities | actors, props, pickups | y (feet) |
| 5 fx_world | muzzle flashes, sparks, smoke, fire | y |
| 6 lighting | light map multiply/add pass | none |
| 7 overlay_world | name tags, health bars, interaction prompts | y |
| 8 ui | HUD, dialogue, menus | widget tree |
| 9 debug | overlays | none |

**Drawables**
- `SpriteDraw(asset, variant, pos, pivot, alpha, tint, flip)`
- `RotatedSpriteDraw(asset, variant, pos, angle, buckets=64)`, using a cache of pre-rotated surfaces per bucket (generalising the guard implementation)
- `TextDraw(key or str, font, pos, colour, shadow)`
- `PolyDraw` / `LineDraw` (debug and procedural FX)
- `CustomDraw(callable)` (escape hatch, counted and warned in stats)

**Camera2D**
- Follow with deadzone and lookahead, world bounds, screen shake (trauma model with decay), zoom (integer-scale preference for pixel art), `world_to_screen` / `screen_to_world`.
- Interpolation uses `clock.alpha`.

**Static layers**
- Levels bake floor and decor into chunked surfaces (e.g. 1024² chunks), keeping the current decor-painter contract: painters read no game state and add no solids.
- Chunks rebuild when the level is edited (hot reload) or when a decor asset is reloaded.

**Post-FX**
- Vignette, grain, flash, colour grade and letterbox as cached surfaces and parameters.
- The inspect-shot vignette and grain move here.

**Lighting integration**
- `engine.lighting` absorbs `lighting.py`: light sources come from `LightSource` components, the light map renders at a configurable downscale, and visibility/occlusion is cached per tile region.
- The "EXPOSED — IN LIGHT / HIDDEN — IN SHADOW" stealth readout becomes a query against the light map (`lighting.sample(x, y)`), not ad hoc logic.

**Stats (debug overlay)**
- Draws per layer, blits, custom draws, cache hits and misses, ms per layer.

**Migration**
1. `LegacyGameScene.draw` first calls the old draw functions inside a single `CustomDraw` on layer 4. Everything still works.
2. Then peel off subsystems one by one (floor/decor → static layers; enemies → GuardRenderSystem; HUD → UI widgets; FX → fx layer), each validated with golden images.

**Acceptance (D6)**
- Golden parity on all gameplay gauntlet shots (tolerance in §9).
- Custom draws are zero in the M5 gameplay scenes by the end of Phase 6.

### 6.7 Render3D bridge and declarative 3D scenes

**Purpose.** Keep `engine3d` (it is good) but stop writing cutscene sets as imperative code with magic numbers.

**Bridge**
- `render3d.bridge`: backend selection (env `ACARISTAN_RENDERER` → settings), renderer pool keyed by size (as `m5martial3d._rend` does now), failure latch with automatic software fallback (as `_cache["failed"]` does now), and `present(surface, buf, x, w)`.
- The existing GL/software parity check (`engine3d_check.py`) becomes part of `ae_ci`.

**Scene3D (data + builder)**
- A 3D set is a list of nodes. Node types:
  - `box`, `quad_xz`, `quad` (any facing), `decal` (asset id, variant, centre, size, facing, bias, emissive)
  - `sprite3d` (glows, halos, window glow)
  - `humanoid` (cast id, outfit, pose ref, position, yaw or `look_at`)
  - `prop_ref` (a reusable sub-set: "tv_set", "desk_lamp", "press_hall_stack_row")
  - `light`, `fog`, `sky`, `rain`
- Values allow **expressions bound to timeline parameters**, e.g. `"x": "lerp(-3.2, -2.9, k)"`, with a tiny safe expression evaluator: arithmetic, `lerp`, `ease_*`, `k`, `t`, named params. No `eval`.

```json
{
  "schema": "ae.set3d/1",
  "id": "m5/vasile_office",
  "fog": {"color": [12,11,10], "start": 8.0, "end": 24.0},
  "light": {"direction": [-0.5,0.7,-0.5], "ambient": 0.42, "diffuse": 0.78, "tint": [1.14,1.0,0.84]},
  "nodes": [
    {"type": "quad_xz", "rect": [-5,-5,5,3.2], "y": 0.0, "color": [40,30,26], "seg": 2},
    {"type": "box", "size": [10,3.2,0.2], "center": [0,1.6,3.2], "color": [44,40,38]},
    {"type": "repeat", "count": 7, "as": "i",
     "node": {"type": "box", "size": [1.6,0.06,0.02], "center": [-1.6, "1.3 + i*0.18", 3.08],
              "color": [110,96,70], "emissive": true}},
    {"type": "decal", "asset": "m5/portrait_frame", "center": [0.2,2.3,3.06], "size": [1.0,1.0],
     "facing": "-z", "bias": 0.5,
     "fallback": [{"type":"box","size":[1.0,1.0,0.04],"center":[0.2,2.3,3.08],"color":[120,96,52]}]},
    {"type": "prop_ref", "ref": "props/desk_with_lamp", "at": [0,0,0.75]}
  ]
}
```

**Builder rules**
- The decal fallback semantics are preserved: `decal` returns False → the fallback nodes are emitted.
- Built meshes are cached per (set id, param hash).
- Golden images must match the imperative originals pixel-for-pixel, within the 3D tolerance.

**Migration**
1. Write a **recorder**: run each existing imperative set builder against a `RecordingRenderer` that logs every primitive call with its arguments.
2. Emit a draft `.set3d.json`.
3. A human-quality pass then factors repeats and `prop_ref`s. The recorder guarantees a correct starting point.
4. Validate with golden frames for every shot that uses the set.

**Acceptance**
- Every M5 3D take renders from data with golden parity (≤ the existing GL/software diff tolerance plus 0.5%).
- `m5martial3d.py` / `m5mid3d.py` shrink to thin timeline bindings, or are deleted.

**Prop quality bar (mandatory — props are built EXTREMELY well, once)**

Reusable props (`prop_ref` targets in `content/props3d/`) are the engine's 3D vocabulary. Every mission that reuses a prop inherits its quality, *and* its flaws. So a prop is not "done" when it looks acceptable in one shot. It is done when it holds up in **any** shot, at any distance, from any angle a camera could plausibly take. Treat each prop as a small shipped product.

1. **Silhouette first.** A prop must read instantly from its silhouette alone, at both close-up and wide-shot size. No plain-box stand-ins: a desk has an inset top, legs or a modesty panel, and drawer fronts; a TV has a bezel, a screen recess, a stand and rear bulk; a lamp has a base, a stem, a shade and a bulb glow.
2. **Layered detail.** Build in three tiers:
   - **primary form** — the big shapes;
   - **secondary form** — bevels faked with thin edge boxes, trims, handles, seams, feet, frames;
   - **surface detail** — decals for labels, wear, grime, scratches, stickers, screws and stencils.
   Nothing ships with primary form only.
3. **Real-world scale.** Model in metres against a reference humanoid (1.78 m). Doors are 2.0–2.1 m, desks 0.74–0.76 m, chairs 0.45 m to the seat, light switches 1.2–1.4 m. A `props3d_lint` check flags any prop whose bounding box falls outside its declared category range.
4. **Pivot and footprint.** The origin sits at floor centre, `+z` is forward, and the prop rests exactly on `y = 0`: no floating, no sinking. Each prop declares its footprint (`[w, d]`), its height and its `anchor`s (`top_surface`, `wall_back`, `seat`, `hand_grip`) so other props and actors can snap to it.
5. **Palette discipline.** Colours come from the shared material palette (`content/props3d/palette.json`: `wood_dark`, `steel_painted_green`, `bakelite`, `concrete_stained`, ...), never from ad-hoc RGB. Every material defines a base colour plus a darker *edge/trim* variant and a lighter *worn* variant, so props look built from materials rather than flat colours.
6. **Era and setting consistency.** Every prop must fit Acaristan: Eastern-bloc, late-20th-century, worn, utilitarian, state-issued. Text on props (labels, stencils, signage) is **English** and goes through the text/localization pipeline where it is legible.
7. **Variants, not copies.** A prop exposes **parameters**, not duplicate files: e.g. `desk(drawers=3, wear=0.6, items=["phone","ashtray"])`, `locker(open=0.0..1.0, dents=2)`, `tv(screen="off"|"static"|asset_id)`. One high-quality definition with variants beats five mediocre near-copies.
8. **Lighting-ready.** Emissive parts (bulbs, screens, dials) are tagged `emissive` and paired with a `sprite3d` glow at a matching tint. Props must look correct under each lighting preset: `night_interior`, `day_interior`, `exterior_overcast`, `exterior_night_rain`.
9. **Budgets.** Every prop declares a primitive count and stays within its tier: `small` ≤ 40 primitives, `medium` ≤ 120, `large`/`hero` ≤ 300. Each prop that has a `lod` variant (fewer primitives, same silhouette) uses it automatically beyond a distance threshold. Detail is spent where the camera looks.
10. **Fallbacks.** Every decal inside a prop has a geometric fallback, so a missing texture never leaves a hole.
11. **Proof sheet: required for every prop.** `python tools/prop_sheet.py <prop_id>` renders a turntable contact sheet:
    - 8 angles × 3 distances (close, medium, wide);
    - each lighting preset;
    - each declared variant;
    - next to the 1.78 m reference humanoid.
    The sheet goes in `previews/props3d/<prop_id>.png`, and its golden image enters regression.
12. **Review gate.** A prop enters the library only after it passes the following nitpick checklist on its proof sheet, with zero S1/S2 issues:

    | Check | Fails if... |
    |---|---|
    | Silhouette | It reads as "a box" at wide-shot size |
    | Scale | It is off against the 1.78 m reference |
    | Grounding | It floats or sinks |
    | Seams | There are gaps or z-fighting between parts |
    | Decals | Decals swim, stretch or are illegible |
    | Palette | It uses colours outside the palette |
    | Lighting | It looks wrong under any lighting preset |
    | Variants | Any variant breaks |
    | Back side | The back is unfinished (all sides are finished unless declared `wall_only`) |

    Record the review in `previews/props3d/REVIEW.md` using the severity scale in Appendix D.
13. **Upgrade in place.** Improve a prop by editing its single definition, never by forking it. Re-run every golden that uses it; the prop-usage index (`tools/prop_usage.py`) lists those shots. Intended visual improvements are re-baselined deliberately, with an ADR-lite note.
14. **Migrated props get upgraded.** When the recorder extracts props from existing M5 sets (`tv_set`, `desk_lamp`, `press_hall_stack_row`, lockers, presses, bales, the tram wreck), the extraction is only a **starting point**. Each one then goes through this bar before entering the library.
    - First, the original shot must match golden. Then the upgraded prop is re-baselined deliberately.
    - Golden parity applies to the *migration* step; quality upgrades are separate, reviewed commits.

**Acceptance (props).** Every library prop has:
- a proof sheet;
- a passing review entry;
- a declared budget, footprint and anchors;
- zero lint errors.

The D2 "Mission 0" uses **only** library props, with no one-off geometry, which proves the library is sufficient by itself.

**3D visual upgrade track (after the data migration — ordered easiest and highest-impact first)**

These upgrades raise the look of every 3D set and cutscene. They are built **on top of** the declarative `.set3d.json` format and the prop library, never as one-off code inside a mission. Do them **in this order**. Each item is its own reviewed commit (or short series), and each one ships with proof sheets and deliberately re-baselined goldens (see "Rules for the whole track" below).

1. **Lighting presets.** Named, saved lighting moods that any set can switch to with one word: `"lighting": "night_interior"`.
   - A preset bundles key light (direction, tint, diffuse), ambient, fog, sky colour, post-FX grade and any default weather. It lives in `content/lighting3d/<id>.preset.json`.
   - Ship at least: `night_interior`, `day_interior` / `office_day`, `exterior_overcast`, `exterior_night_rain` / `rainy_street`. Aliases are allowed; duplicate definitions are not.
   - A set may override single fields on top of a preset. Timeline `light` tracks can cross-fade between two presets (`"preset_blend": ["office_day", "night_interior", "k"]`).
   - These are the same presets the prop quality bar (rule 8) and the proof sheets already test against. This step makes them real data instead of a checklist.
2. **Several lights per scene.** Real point and spot lights (lamps, screens, windows, bulbs) that light what is near them, in addition to the one key light.
   - New node: `{"type": "light", "kind": "point|spot", "pos": [...], "color": [...], "intensity": ..., "range": ..., "cone": ...}`. Emissive prop parts can declare an attached light, so a `desk_lamp` lights its desk wherever it is placed.
   - Distance falloff and a per-set light budget (start at 8 active lights; the closest/strongest win, chosen per object). Both backends must support it.
   - Software backend: per-vertex lighting is acceptable. GL backend: per-pixel is allowed only if the parity tolerance still holds or the difference is recorded in an ADR.
3. **Soft shadows under objects.** Blurred dark patches under furniture, props and humanoids, so nothing looks like it is floating.
   - Implemented as a cached, blurred projected quad (blob or footprint-shaped) per object, using the prop's declared footprint. Humanoid feet get their own small contacts.
   - Cheap, works on both backends, and it is the biggest visual win per hour. It is on by default.
4. **Corner darkening (ambient occlusion).** Darker corners and seams where walls meet floors and where objects touch surfaces.
   - First version: **baked**. Vertex darkening or AO strips/decals generated when a set is built, cached with the mesh (set id + param hash). No per-frame cost.
   - Optional later: screen-space AO on GL only, behind a setting.
5. **Cinematic camera effects.** A per-shot post-FX stack: depth-of-field blur behind (or in front of) the subject, slight lens distortion, film grain, per-scene colour grading, vignette (dark edges) and bloom around bright and emissive things.
   - Each effect is a timeline-keyable parameter on the camera track (`dof_focus`, `dof_strength`, `grain`, `vignette`, `bloom`, `grade`). Colour grades are LUT or curve assets in `content/grades/`.
   - Grain must use a seeded RNG stream so goldens stay deterministic. Accessibility settings can turn grain and distortion down or off; flash reduction also caps bloom.
6. **Weather and atmosphere.** Better rain (streaks, splashes, depth layers), layered/height fog, dust in light beams, smoke, steam from vents and puddle reflections.
   - Each is a node type or an emitter prop (`rain`, `fog_layer`, `light_shaft`, `smoke_emitter`, `steam_vent`, `puddle`). They are seeded, timeline-driven and budgeted.
   - Puddle reflections: start with a faked mirrored/darkened copy of nearby emissives and the sky. A true reflection pass is GL-only and optional.
7. **Real cast shadows.** Proper shadows thrown by the one main (key) light.
   - Expected to be **GL-only** (shadow map). The software backend keeps the soft contact shadows from step 3 as its fallback.
   - This breaks pixel parity on purpose, so it needs an ADR first: parity is checked with cast shadows **off**, and GL-with-shadows gets its own golden set.
   - Must be decided by measurement: if it cannot hold the 3D frame budget on the reference machine, it stays a setting that is off by default.
8. **More character polish.** Facial expressions, mouths that move with dialogue, and eyes and heads that follow the camera or another character.
   - Expressions are named face assets (`neutral`, `angry`, `afraid`, `smirk`, ...) on the rig, keyable on actor tracks.
   - Mouth movement is driven from dialogue lines (text-timed visemes or audio amplitude), with no hand-keying per line.
   - Head/eye look-at: `look_at: "camera" | "<actor id>" | [x,y,z]` with clamped angles and smoothing, added on top of the pose blend.
9. **Textures on surfaces.** Brick, concrete, wood grain, tile and wallpaper on walls and floors instead of flat colours.
   - Textures are assets in the pipeline (§6.5) and are referenced from the material palette (`content/props3d/palette.json` gains an optional `texture` per material), so props and sets pick them up without per-mission changes.
   - Software backend: UV-mapped and pixel-scale friendly (nearest filtering, small tiles). Keep the upper-left key light rule in baked texture shading.
10. **Animated props.** Doors that open, flickering lights, moving machine parts, a TV playing footage, spinning fans.
    - Props declare named animated parts and channels (`door.open`, `fan.spin`, `bulb.flicker`, `tv.screen`). Timelines key them, or they run on their own clock with a seed.
    - A flickering bulb drives both its emissive glow and its attached light from step 2. A TV screen plays a sprite-sheet or a 2D render-to-texture clip.
11. **Importing models from Blender.** Build complex props in a real 3D tool and bring them in.
    - Pick one documented format (glTF 2.0 / `.glb` preferred; OBJ as a minimum), import it through the asset pipeline into the engine's mesh format, and bake it so the game never parses glTF at runtime.
    - Imported props still go through the full prop quality bar, palette mapping, scale lint and triangle budget.
    - This is the biggest step and the most work. Write an ADR on format, scale and axis conventions before starting.

**Rules for the whole track**
- **Data first.** Every upgrade is reachable from `.set3d.json`, prefab/prop definitions or timeline tracks. A mission must never need Python to use one.
- **Both backends, or a declared fallback.** The software backend is still the CI oracle. Any GL-only feature (cast shadows, SSAO, true reflections, per-pixel lights) has a documented software fallback, an ADR and its own golden set. The existing GL/software parity check runs with GL-only features **off**.
- **Settings and budgets.** Every upgrade has a quality setting (off / low / high) in §6.18 and a cost measured with the §6.22 bench. Nothing on by default may push a 3D shot past its frame budget.
- **Deliberate re-baselining.** These are intended visual changes. Golden images are re-captured on purpose in a dedicated commit, with before/after proof sheets in `previews/upgrades3d/<step>/` and an ADR-lite note. Never re-baseline in the same commit as an unrelated change.
- **Determinism.** Grain, flicker, rain, smoke and dust all use named, seeded RNG streams so goldens and replays stay reproducible.

**Acceptance (upgrade track).** For each step that ships:
- it is usable from data alone, demonstrated in Mission 0 or a gauntlet shot;
- it has a proof sheet, a passing review entry (Appendix D scale), a setting and a bench number;
- `ae_ci` passes, including parity (GL-only features off) and the re-baselined goldens.

### 6.8 Animation
- **Clips:** sprite-sheet animations with per-frame duration and frame events (footstep, muzzle). Animator component with a state machine (idle/walk/aim/hit/die), transitions and blend-free crossfade (alpha or a cut).
- **Pose cache:** generalise `artpack.pose(key, size, painter)` into `anim.pose_cache` with an LRU bound, stats and a **bake hook**, so hot poses can be baked like the M5 Maru headings (36 headings × 2 strobes). It must work for figure_kit bodies (`draw_character`) and HQ cast looks.
- **Tweens:** `tween(obj_or_component, "field", to, dur, ease)` for UI and juice, running on the real or sim clock by choice.
- **Rig poses for 3D:** pose dictionaries (`spine`, `head_p`, `lsh_p`, `lel`...) become named pose assets (`content/poses/*.pose.json`) with blending (lerp per joint) for timeline actor tracks.

### 6.9 Physics, collision, navigation
- `TileMap` holding solid flags per tile (from the level), with fast queries `solid_at(tx, ty)`, `rect_hits(rect)` and `raycast(a, b)` (DDA on the grid).
- `SpatialHash` for entity–entity queries (cell = 2 tiles).
- Movement: `Kinematics` (velocity, max speed, friction) + `Collider` (circle or AABB). The collision system resolves with axis-separated slide. Behaviour must match the current player and enemy movement **exactly** (parity test: record a 30 s input stream and compare positions per frame against the legacy implementation).
- Line of sight: grid raycast plus optional "soft cover" tiles.
- Navigation: A* on the tile grid with path caching keyed on (start, goal, grid version). The existing `_walk_grid_cache` in `enemy_ai` becomes `nav.GridGraph`. Optionally flow fields toward the player for crowds, behind a flag.
- Triggers: rect/poly regions from the level that emit `TriggerEntered` / `TriggerExited` for entities with the matching tags.

### 6.10 Input
- An **action map**: `move_x`, `move_y` (axes), `aim` (mouse or right stick), `fire`, `reload`, `interact`, `swap`, `pause`, `skip`, `confirm`, `back`, `debug_console`, `debug_overlay`.
- Bindings live in `settings/input.json`, rebindable in the menu, and are saved.
- Contexts: gameplay, dialogue, cutscene (skip/confirm only), menu, console (captures all text). The scene stack activates contexts.
- Gamepad support (pygame `joystick`/`controller`), hotplug and dead zones.
- **Recording**: per-step action snapshots for replays and tests (`input.record` / `input.playback`).
- "Any key skips" behaviour (the current inspect shots) becomes the `skip` action plus mouse click, configurable.

### 6.11 Audio
- Buses: master, music, sfx, voice, ui. Per-bus volume and ducking rules (music ducks −8 dB under dialogue voice or text blips).
- Positional SFX: pan and attenuate by distance from the listener (camera centre), with a max number of voices per sound id and priority stealing.
- Music: playlists per scene, crossfades, stingers on events (alarm, raid start).
- Optional sounds (seen: `Loaded optional sound 'mission3_alarm_loop'`) become manifest entries with `optional: true`. A missing optional sound logs once and plays silence.
- Headless: a null backend for tests.

### 6.12 UI toolkit
- A retained widget tree per scene: layout (anchors, stacks, padding), theme (fonts, colours, nine-slice frames as baked sprites) and input focus.
- **Standard widgets are extracted from what the missions already draw (then the duplicates are deleted):**
  - `DialogueBox`: speaker plate, colour per speaker, wrapped text with typewriter reveal, "continue" prompt, the "ANALYZING FILE..." waiting state. This is a game-wide convention, so keep it as a theme option.
  - `HudPlate`: the M4/M5 hold-bar plate (title, progress bar, right readout, optional HEAT pips). The baked frame from `art/m5/plate.py` becomes the theme's plate skin.
  - `MagIcons`: stick or box mag shells (baked) plus a live round overlay.
  - `ObjectiveBanner`, `NameTag`, `HealthBar`, `InteractPrompt`, `Minimap`, `HostilesCounter`, `StealthIndicator`, `Toast`, `Menu`.
- Text uses `engine.text.layout` (wrap, fit-to-box, ellipsis), so overflow cannot happen silently: in dev, overflow raises a visible red outline plus a log warning.
- UI scale setting (1×, 1.5×, 2×) with crisp integer scaling of pixel fonts where possible.

### 6.13 Text and localisation
- String tables: `game/content/strings/en.json` (`"m5.caption.notice": "Every name crossed out. Mine's still there. For now."`).
- `T("key", **fmt)` with fallbacks. Missing keys show `⟦key⟧` in dev and English in release.
- Baked art declares the string keys it uses (manifest `strings`). Changing a string invalidates the bake hash.
- Font registry with glyph-coverage checks (the existing `font_glyph_coverage` smoke check moves here).
- The policy is **English-only for now**, but the architecture is ready for more languages. Do not translate. Just make it possible.

### 6.14 Dialogue
- Format: `.dlg.json`, or a minimal line-based script format compiled to JSON. Nodes have a speaker, a text key or literal, optional choices, conditions (`flag("met_kovac")`, `var("heat") > 2`), effects (`set`, `emit`, `objective`) and timing hints (auto-advance ms, "can't continue until" for scripted holds).
- `DialogueRunner` drives `ui.DialogueBox`, emits `DialogueLine` / `DialogueEnded` and is skippable according to the rules.
- A validator checks: unreachable nodes, missing speakers, missing string keys, lines too long for the box at the current font (using the text-fit layout).
- Migration: extract the existing mission dialogue (cutscene lines, HQ chatter, NPC barks, inspect captions) into dialogue and string files, using a script-assisted extraction plus a manual review. Keep IDs stable.

### 6.15 Cutscene timeline (the crown jewel)

**Purpose.** Cutscenes are the game's signature. Make them **authorable, scrubbable and data-driven**, without losing a single frame of quality.

**Model**
```
Timeline
  id, duration_ms, fps_hint, letterbox, ui_composite(bool), skippable(bool)
  set: set3d id (3D) | layer stack (2D) | split: [left set, right set] (e.g. m5_radio)
  params: named values (k = normalised progress of a clip, etc.)
  tracks:
    camera   : keys {t, pos, target, fov, ease, shake{amp,freq,seed}, handheld{hh, seed}}
    actor[n] : {cast, outfit, spawn{pos,yaw}} + keys {t, pos, yaw|look_at, pose(ref|inline), blend}
    light    : keys {t, ambient, diffuse, tint, direction}
    fx       : clips {start, end, kind(halo|glow|rain|flash|smoke), params}
    decal    : visibility/emissive keys for set nodes
    dialogue : clips {start, node_id | text_key, speaker, hold_until_input}
    audio    : clips {start, sound|music, bus, fade}
    event    : markers {t, name, payload}  → TimelineMarker events
    caption  : the bracketed stage-direction captions ("[ The doors come in. ... ]")
```

**Player**
- Deterministic sampling at any `t` (seek, scrub, step).
- Handheld/shake noise is seeded per track, so frames are reproducible. This matches the current `_cam(..., hh=0.007, seed=10)` behaviour.
- The cutscene renders through `render3d.bridge`, composites UI (dialogue box, location tag "SAFEHOUSE // KRAP FLAT 4C", caption) and reports timing per frame.

**Editors** (§6.20)
- A scrub bar, a camera fly mode, "set key here", and a nudge for actor positions.
- **Writes back to the JSON file**, preserving formatting and key order (stable output, minimal diffs).

**Migration**
1. Use the same recorder approach as §6.7. Run each imperative take function at the gauntlet's sample times, capture camera, actor, light and FX parameters, and fit keys. Linear segments are detected. Easing is inferred from known helpers (`_k(t, start, len)`, `lerp`, smoothstep). Unknown curves are captured as dense keys and flagged for a human pass.
2. Validate each migrated take against the gauntlet golden frames at the same `t`.
3. Shot tags (`in00`… `end04`) become timeline ids. The gauntlet consumes timelines directly.

**Acceptance**
- Every M5 take (30 shots) plays from timeline data with golden parity.
- Takes for M1–M4 are migrated or wrapped by adapters listed in ADAPTERS.md.
- The camera editor round-trips: open, move a key, save, reload, and the frame changes exactly as expected.

### 6.16 Levels
- Format: `.level.json` (native) plus an importer for **Tiled JSON (.tmj)**, so a real editor can be used without new runtime dependencies.
- Contents:
  - tile layers (floor, walls with solid flags, overlay)
  - object layers (spawns with prefab ids and overrides, NPCs, props, pickups)
  - triggers/regions (stage transitions, dialogue starts, inspect points)
  - paths (patrols, the convoy route), light sources, decor placements (asset id, variant, position, layer)
  - stage metadata (objective text key, music, ambient, weather: rain on/off and density)
- Decor painters (`decor_paint`, `decor_interior`) become **decor asset definitions plus placements**. Painters that are truly procedural (tyre marks, scattered leaflets with a seed) become `procedural_decor` entries with a seed and parameters, executed at static-layer bake time. Keep the RNG stream parity rule (R2).
- Migration: an exporter converts the current string grids and the hard-coded placement code into level JSON. Re-load from JSON and diff the static layer pixel-for-pixel against the legacy painter output.

### 6.17 Save/load and determinism
- Snapshot = serialised world (components with versioned schemas), scene stack summary, mission vars and flags, RNG stream states, clock frame. Checkpoints use the same format (the existing M5 checkpoints and Maru-fail flow become save-system users).
- `statehash(world)`: a stable hash of sorted component data. Floats are quantised to 1e-4 to absorb benign float noise; document why.
- **Replay check:** record inputs for N seconds from a checkpoint, replay them, compare state hashes every 60 steps, report the first divergence with a diff of component values.

### 6.18 Settings
- Layered: defaults (code) < `settings/settings.json` < env (`ACARISTAN_*`) < CLI flags.
- Typed schema: video (renderer gl/software/auto, scale, vsync, fullscreen), audio (bus volumes), gameplay (aim assist, subtitles always on), accessibility (screen-shake scale, flash reduction, text speed, high-contrast UI), dev (debug overlay, hot reload, golden capture).
- `SettingsChanged` events make systems react live.
- **Accessibility is a first-class requirement:** flash reduction must cap the breach-light white-out (mid17 is nearly a full white frame), and shake scale must apply to cutscene handheld noise too.

### 6.19 Debug tools
- **Overlay (F3):** frame-time graph (sim / render / present split), spike markers (the gauntlet saw 85 ms spikes in mid17), per-layer render stats, cache stats, entity count, current scene stack, active input context.
- **Entity inspector:** click an entity to see its components, live-edit fields (dev), and jump to its prefab.
- **Collision/nav view:** solid tiles, colliders, LOS rays, current A* paths, trigger regions.
- **Console (`~`):** `scene push <id>`, `timeline play <id> [t]`, `spawn <prefab> [x y]`, `give ammo`, `heat 3`, `seed`, `reload assets`, `golden capture`, `events tail`, `bench <scene>`.
- **Capture:** single screenshot, image sequence, and "capture gauntlet frame" with an exact `t` for timelines.

### 6.20 Editors (dev-only, inside the game window)
- **Camera editor:** WASD/mouse fly, FOV wheel, snap the target to an actor, "add or replace camera key at t", ghost frustum for neighbouring keys, UI-composite toggle so dialogue-box occlusion is checked while editing. The end01 scope readout hidden behind the dialogue box was exactly this class of bug.
- **Timeline editor:** scrub, play range, per-track key list, nudge values, add markers, save.
- **Level viewer:** layers on/off, trigger listing, spawn preview, "reload level".
- Rule: editors write **data files only**, never Python.

### 6.21 Testing strategy
| Layer | What | Tool |
|---|---|---|
| Unit | core (clock, rng, events), physics (sweeps, raycasts), text layout, schema validators, expression evaluator | `tests/unit/*` (stdlib `unittest`, no pytest dependency unless approved) |
| Contract | boundary lint, public-API snapshot (`__all__` diff vs `docs/engine/api_snapshot.txt`) | `check_boundaries.py`, `ae_api_snapshot.py` |
| Smoke | the existing `smoke_test.py` checks, extended per subsystem | `smoke_test.py` |
| Data | validate every content file, assets resolve, string keys exist, dialogue fits | `ae_validate.py` |
| Bake | staleness, determinism (bake twice → identical bytes), asset lint | `ae_bake.py --check --lint` |
| 3D parity | GL vs software diff | `engine3d_check.py` |
| Golden image | cutscene frames at fixed t, gameplay shots at fixed seeds and inputs | `ae_golden.py` (§9) |
| Replay | deterministic state hashes | `ae_replay_check.py` |
| Bench | budgets | `ae_bench.py` |
| One command | everything above, with a summary table and a non-zero exit on any failure | `ae_ci.py` |

### 6.22 Performance budgets (reference machine = the dev machine; record its specs in STATUS.md)
| Scenario | Budget |
|---|---|
| Gameplay frame (M5 quarter, rain, 6 guards, fire FX), software 2D | ≤ 10 ms update+render at 1000×700 (target 60 fps with headroom) |
| Fixed sim step (60 Hz) | ≤ 3 ms average, ≤ 6 ms p99 |
| Cutscene frame, GL backend | ≤ 33 ms average, no frame > 50 ms after warm-up (the gauntlet saw 85 ms in mid17: profile and fix) |
| Cutscene frame, software backend | ≤ 50 ms average (fallback quality is acceptable) |
| Scene transition (cold) | ≤ 400 ms including asset preload for one mission stage |
| Bake all packs | ≤ 60 s full, ≤ 5 s incremental (one asset changed) |
| Memory | ≤ 600 MB RSS for any single mission stage |
| Tolerance | CI fails when a budget is exceeded by > 10% over three consecutive bench runs |

Profiling rules:
- Measure first (`profiling.scope("name")`).
- Optimise hot paths with caching and batching before cleverness.
- Never trade determinism for speed.

### 6.23 Logging and errors
- Channels: `core`, `scene`, `assets`, `render`, `render3d`, `audio`, `input`, `world`, `ai`, `dialogue`, `timeline`, `save`, `tools`.
- Levels: debug, info, warn, error.
- Dev builds log warnings on screen as toasts (rate-limited).
- **Warn once** helpers for recurring fallbacks: missing optional sound, GL fallback, sprite fallback to live render.
- Engine exceptions carry context (asset id, timeline id and t, entity id).

### 6.24 Packaging (later phase)
- `tools/ae_package.py` builds a distributable folder with only baked assets (no `render()` modules needed at runtime unless dev) and a version stamp.
- Release mode turns off hot reload and editors and switches fallbacks to silent.
- Optional freezing (PyInstaller) behind an ADR. Not required for "done".

---

## 7. Migration plan (phases)

Each phase lists **Entry**, **Work**, **Deliverables** and **Exit criteria**. Never start a phase before the previous exit criteria hold. Every phase ends with a phase report (Appendix F) and an update to `docs/engine/STATUS.md`.

### Phase 0 — Audit, baseline, hygiene (no behaviour changes)
**Entry:** clean checkout, smoke test green.

**Work**
1. Inventory every file under `src/` and `tools/`: path, lines, top-level defs, imports.
2. Build the import graph and highlight shared → mission edges (the boundary violations to remove).
3. **Global-state census:** every `STATE.<field>` read and write, with file:line, grouped by owner mission and by subsystem.
4. **Duplication census:** HUD/plate/mag-icon/dialogue/name-tag drawing duplicated across missions (similar-function detection with normalised AST hashing).
5. **Draw census:** generalise `m5_draw_audit.py` to all missions and rank the procedural draw functions by draw calls.
6. **Cache census:** every module-level cache dict (`_CACHE`, `_cache`, `_MAG_SPRITES`, `_static`, `_GUARD_ROT`, `_DROP_SHADOW_CACHE`, ...): what it keys on and when it invalidates (usually never).
7. Normalise line endings and encoding repo-wide in **one dedicated commit** (`.gitattributes`: `* text=auto eol=lf`, with `*.png binary` etc.). Run all tests before and after: zero behaviour change.
8. **Golden baseline:** capture golden images for every cutscene shot at three times each (25%, 50%, 75%) plus all gameplay gauntlet shots, with the current code. Store them under `tests/golden/baseline_v0/` with a manifest (shot id, t, renderer, seed, resolution). This is the parity oracle for every later phase.
9. **Replay baseline:** add a minimal input recorder to the legacy loop (dev flag) and record one 30–60 s segment per mission from a checkpoint, with legacy position/state snapshots every second.
10. Write `docs/engine/AUDIT.md`, `STATUS.md`, `BUGS.md`, `ADAPTERS.md` (empty table), `adr/ADR-000-template.md`, and the first ADRs: ADR-001 (package layout: `game/` vs keeping `missions/`), ADR-002 (ECS-lite design), ADR-003 (data formats: JSON + optional Tiled import).

**Exit**
- AUDIT.md complete (with counts).
- Golden and replay baselines captured, and reproducible: re-capturing gives identical images, or diffs within the 3D tolerance for GL.
- Line endings normalised.
- All tests green.

### Phase 1 — Kernel: App, Clock, Services, no import side effects
**Work:**
- `engine.core` (app, clock, events, rng, log, config, services, profiling, errors).
- Move display creation into `App.boot`.
- Remove import-time `SDL_VIDEODRIVER` setdefaults.
- Run the legacy game inside `LegacyGameScene` on the fixed-step loop.
- Route all `random` use in simulation through named rng streams, keeping each mission's legacy seeding so parity holds.

**Exit**
- Import-side-effect test passes.
- Golden and replay baselines are identical.
- Crash report works.
- `ae_ci.py` exists (it runs smoke, compileall and boundary lint, in warn mode for now).

### Phase 2 — Boundary and scene stack
**Work:**
- `engine.scene`. Convert boot/menu/mission/pause into scenes.
- Wrap the cutscene dispatcher in `CutsceneScene` and `inspect_fpv` in `InspectScene`.
- `check_boundaries.py` in **enforce** mode for `engine/*`.
- Move shared modules that are really engine code (`render_util`, `lighting`, `artpack`, `sprite_lib`, generic parts of `figure_kit`) under `engine/`, leaving re-export shims at the old paths with deprecation warnings.

**Exit**
- Scene trace for an M5 playthrough matches the expected trace.
- Boundary lint enforced and passing.
- Golden and replay parity.

### Phase 3 — Asset pipeline (game-wide)
**Work:**
- `engine.assets` with manifest, registry, bake, hashing, hot reload and lint.
- Migrate `src/art/m5` (125 assets) with shims.
- Run the draw census on M1–M4 and convert the top-ranked props and HUD art per mission (target ≥ 80% of procedural draw calls by count in static or semi-static art).
- Replace all ad hoc caches with registry or pose-cache usage.

**Exit**
- D5 holds.
- `ae_bake --check --lint` clean (lint warnings are triaged into BUGS.md).
- Golden parity.
- Hot reload demo works (change a poster colour, see it live in a running cutscene and in gameplay).

### Phase 4 — UI toolkit and text
**Work:**
- `engine.ui`, `engine.text`.
- Extract DialogueBox, HudPlate, MagIcons, ObjectiveBanner, NameTag, HealthBar, Prompt, Minimap, Hostiles and StealthIndicator from the missions.
- Delete the per-mission duplicates.
- String tables for all player-facing text.

**Exit**
- Zero duplicated HUD code across missions (duplication census re-run).
- Text-fit validation passes for every string in every widget it appears in.
- Golden parity (UI-composite cutscene frames included).

### Phase 5 — World/ECS-lite and standard systems
**Work:**
- `engine.world` and the std components and systems.
- Adapters for legacy `Enemy` and player objects.
- Migrate movement, collision, combat, AI hosting, interaction, NPCs, pickups, props.
- Remove attribute stuffing.

**Exit**
- D4 holds.
- Replay parity for every mission segment (state hashes match the legacy snapshots, translated through the adapters).
- Component dump tool works.

### Phase 6 — Render2D queue, camera, static layers, lighting, post-FX
**Work:**
- `engine.render2d` and `engine.lighting`.
- Move each gameplay draw path into systems that submit drawables.
- Bake static layers from level decor.
- The camera handles shake, follow and interpolation.

**Exit**
- D6 holds (zero custom draws in M5 gameplay; ≤ 5 documented custom draws elsewhere, each with a removal ticket).
- Golden parity.
- Gameplay budget met.

### Phase 7 — Data-driven levels and dialogue
**Work:**
- `engine.level` (+ Tiled importer) and `engine.dialogue`.
- Export all mission maps, placements, triggers and patrols to level JSON.
- Extract dialogue to `.dlg.json` and string tables.
- The validators join CI.

**Exit**
- Every mission loads its levels from data.
- Static-layer pixel parity with the legacy painters.
- Dialogue validator clean.
- Replay parity.

### Phase 8 — Declarative 3D sets and cutscene timelines
**Work:**
- `render3d.scene3d`, `timeline.*`, the recorder-based migration of every 3D take, and the 2D cutscene layer stacks.
- `CutsceneScene` plays timelines only.
- The gauntlet reads timelines.

**Exit**
- Every cutscene shot matches golden (3D tolerance).
- Imperative take modules removed, or reduced to custom FX hooks registered by id (documented).
- Camera editor round-trip works.

### Phase 9 — Save/load, determinism hardening, settings, accessibility
**Work:**
- `engine.save`, state hash, `ae_replay_check`.
- Layered settings.
- Accessibility (flash reduction, shake scale, text speed, subtitles).
- Input rebinding UI and gamepad support.

**Exit**
- D8 holds.
- Settings persist and apply live.
- Flash-reduction cap verified on the mid17 breach frames (max frame luminance under the threshold when enabled).

### Phase 10 — Tooling polish, docs, Mission 0, final gate
**Work:**
- Debug overlay, console and inspector complete.
- Timeline and level editors.
- `ae_new_mission.py` scaffolder.
- Write the "add a mission" tutorial, **then build Mission 0 by following it literally**. Fix the tutorial wherever reality differs.
- Benches, packaging script, final docs.

**Exit:** §13 final acceptance.

### Phase 11 — 3D visual upgrades
**Entry:** Phase 8 exited (every 3D take renders from data with golden parity). Prop library acceptance met.

**Work:** the §6.7 "3D visual upgrade track", **in its listed order**:
1. Lighting presets
2. Several lights per scene
3. Soft shadows under objects
4. Corner darkening (baked AO)
5. Cinematic camera effects (DOF, lens distortion, grain, grading, vignette, bloom)
6. Weather and atmosphere
7. Real cast shadows (GL-only, behind an ADR)
8. Character polish (expressions, lip movement, look-at)
9. Surface textures
10. Animated props
11. Blender model import

Steps 1–4 are the minimum for this phase to exit. Steps 5–11 may continue after Phase 10, but each one that starts must finish to the track's acceptance bar before the next begins.

**Exit**
- Steps 1–4 shipped to the track's acceptance bar, with before/after proof sheets.
- Every 3D shot re-baselined deliberately and reviewed; no new S1/S2 issues in a gauntlet pass.
- Parity check green with GL-only features off; 3D bench within budget at default settings.

> **Parallelism.** Phases 3 and 4 may overlap once Phase 2 exits. Phase 7 (levels) can start after Phase 5. The dialogue half of Phase 7 can start after Phase 4. Phase 8 needs Phases 3 (decals as assets) and 4 (UI composite). Phase 11 needs Phase 8, and can run alongside Phases 9–10 because it touches only `render3d`, `content/` and goldens. Never parallelise two phases that touch the same files without a written merge plan.

---

## 8. The working loop (every task, every time)

1. **Orient.** Re-read STATUS.md, the current phase's exit criteria and any relevant ADRs. State the task in one sentence.
2. **Locate.** Find every call site and dependency (search the `*.py` sources, not `.pyc`). List them in the task note.
3. **Plan.** Write the smallest change that moves one exit criterion forward. Name the parity evidence you will produce (which golden shots, which replay segment, which test).
4. **Test first where possible.** Add or extend the unit, contract or smoke check that will prove the change.
5. **Change.** Small commits. Keep the legacy path as a fallback until parity holds. Match line-ending and formatting rules.
6. **Verify.** Run `ae_ci.py`, or, for quick iterations, the subset plus the full smoke test before you commit. For anything visual, render the before and after images and *look at them*. A passing number is not a substitute for looking.
7. **Log.**
   - Update STATUS.md (checkbox), ADAPTERS.md (if you added or removed an adapter) and CHANGELOG.md (if behaviour changed deliberately).
   - Add BUGS.md entries for anything found.
   - Write an ADR if you made an architectural choice.
8. **Report** in the format below.

**Task report format (print at the end of every task):**
```
TASK: <one line>
PHASE: <n> — exit criteria advanced: <ids>
CHANGED: <files (+/- lines)>
EVIDENCE:
  - tests: <command> → <result line>
  - golden: <n shots compared, max diff, worst shot id>
  - replay: <segment ids, hash match yes/no>
  - images reviewed: <paths>
RISKS / CAVEATS: <first, honestly>
ADAPTERS: added <..> removed <..>
NEXT: <the next smallest step>
```

**When you are stuck** (the same failure twice):
- Stop.
- Write down the hypothesis, what you tried and what you observed.
- Reduce to a minimal reproduction.
- Consider reverting to the last green state.
- Never "fix" a parity failure by re-baselining the golden image unless the change was deliberate and is logged in CHANGELOG.md with before and after images.

---

## 9. Golden-image regression (the visual oracle)

- **Capture spec:** `{id, kind: cutscene|gameplay|inspect|ui, source (timeline id / level+checkpoint), t_ms or input-script, seed, renderer, resolution, settings_profile}`.
- **Comparison:**
  - per-pixel absolute difference, reporting max, mean and the percentage of pixels with diff > 8;
  - SSIM-lite (block luminance correlation) for 3D frames;
  - output: a diff heatmap image next to each failure.
- **Tolerances:**
  - 2D gameplay and UI: **exact** (0 differing pixels), except declared animated regions (rain, flicker), which are masked by a mask image per shot.
  - 3D cutscenes (same backend): ≤ 0.5% of pixels over 8, mean diff ≤ 0.6.
  - Cross-backend: governed by `engine3d_check` (existing worst-diff threshold, ~4%).
- **Re-baselining** needs: a CHANGELOG entry, the before and after images, and a reason (deliberate change or bug fix).
- The **gauntlet** (cycle renders, nitpick log, S1–S3 severities, kill criteria) stays the human QA ritual. Golden images are the automated guard that stops a fixed nitpick from coming back.

---

## 10. Banned patterns (fail review on sight)

1. New fields on `STATE` or any other global. Use scene, world, mission vars or services.
2. `getattr(obj, "_x", default)` / `obj._x = ...` attribute stuffing on shared types.
3. Shared/engine code that names a mission (`"m5"`, `mission5_stage`, `STAGE_RAID`) anywhere except data-driven registries.
4. `pygame.draw.*` / `surface.blit` onto the screen from gameplay code outside render systems or asset definitions.
5. Raw `pygame.image.load`, `pygame.font.Font(...)` or `pygame.mixer.Sound(...)` outside `engine.assets` / `engine.text` / `engine.audio`. (The tram tag currently calls `pygame.font.Font(None, 40)` inside an asset painter; route it through `engine.text.fonts`.)
6. Unseeded randomness, or `time.time()` in simulation.
7. Module-level caches with no invalidation. Register them with the asset or pose cache, which owns invalidation.
8. Import-time side effects (windows, asset loads, env mutation).
9. Copy-pasting UI or HUD between missions ("ported from M4, values local").
10. Magic camera or set numbers in Python for cutscenes after Phase 8. They belong in data.
11. Catch-all `except Exception: pass` without a warn-once log. (Several current fallbacks do this. Make them log once, with context.)
12. "Fixing" a failing golden image by re-baselining it silently.
13. Committing on red.
14. Claiming VERIFIED without an evidence path.

---

## 11. Risk register (keep it updated in STATUS.md)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Parity drift during the ECS migration (subtle movement/AI differences) | High | High | Replay baselines before Phase 5; adapters; per-frame position compare; migrate one system at a time |
| RNG stream divergence when painters become assets | High | Medium | Preserve consumption order (bale precedent); per-subsystem named streams; golden static-layer diffs |
| GL backend nondeterminism across drivers | Medium | Medium | Golden tolerances for 3D; software backend as the canonical oracle for CI |
| Recorder-based cutscene migration misses implicit state (closures, caches) | Medium | High | Record at many t values; compare frames, not just parameters; flag dense-key tracks for a manual pass |
| Performance regressions from the abstraction layers (Python overhead) | Medium | Medium | Bench in CI; batch submits; cache rotated sprites; profile before optimising |
| Scope explosion ("while I'm here") | High | Medium | R16; BUGS.md; phase discipline |
| Tooling timeouts on long jobs | High | Low | Background processes plus log polling; split long jobs |
| Mixed line endings breaking edit tools | Certain (until Phase 0) | Low | Phase 0 normalisation commit |
| Authorial intent lost when converting cutscenes to data | Medium | High | R17; golden parity; human review of the factored set/timeline files |
| 3D visual upgrades break parity or blow the frame budget (cast shadows, per-pixel lights, post-FX) | High | Medium | Software backend stays the oracle; GL-only features off for parity, own golden set; quality settings; bench every step |
| Visual upgrades silently change cutscene look / authorial intent | Medium | Medium | Deliberate re-baseline commits with before/after proof sheets; per-shot overrides; human review |

---

## 12. Architecture Decision Records

Every non-obvious choice gets an ADR in `docs/engine/adr/ADR-NNN-title.md`:

```
# ADR-NNN: <title>
Status: proposed | accepted | superseded by ADR-MMM
Date: YYYY-MM-DD
Context: <forces, constraints, evidence (measurements, file refs)>
Decision: <what we do>
Alternatives considered: <option — why not>
Consequences: <good, bad, follow-ups>
Verification: <how we will know it was right>
```

Mandatory early ADRs:
- 001 package layout
- 002 ECS-lite
- 003 data formats
- 004 fixed timestep
- 005 asset ids and hashing
- 006 golden tolerances
- 007 expression language for sets and timelines (grammar, safety)
- 008 Tiled import scope
- 009 UI theme and pixel-scaling policy
- 010 save format and versioning
- 011 lighting presets and multi-light model (falloff, light budget, software vs GL shading)
- 012 GL-only 3D features policy (cast shadows, SSAO, reflections: fallbacks, parity, goldens)
- 013 3D model import (format, scale, axes, baking)

---

## 13. Final acceptance (stopping condition)

You may declare Retardovici Pulse Engine 6 Gold complete **only** when one final `python tools/ae_ci.py` run, on a clean checkout, prints a table in which every row is OK:

```
AE CI SUMMARY
compileall ............................ OK
boundary lint (enforce) ............... OK   0 violations
api snapshot .......................... OK
unit tests ............................ OK   N passed
smoke test ............................ OK   (SMOKE TEST: OK)
data validation ....................... OK   levels L, timelines T, dialogue D, prefabs P
asset bake check + lint ............... OK   A assets, 0 stale, 0 lint errors
engine3d parity ....................... OK   worst diff x.xx%
golden images ......................... OK   G shots, 0 failures
replay determinism .................... OK   R segments, hashes match
bench budgets ......................... OK   all within budget
mission 0 (zero engine diffs) ......... OK
```

…**and** the final report demonstrates D1–D12 with evidence links, **and** a fresh human-style gauntlet pass (every cutscene shot at two new t values, every gameplay shot) finds no new S1/S2 issues.

If you stop before this, your final message must say so plainly in the first line, list the exit criteria that are not met, and give the next three concrete steps.

---

## Appendix A — Code skeletons

### A.1 Component and system
```python
# engine/world/component.py
from dataclasses import dataclass, field, fields
_REGISTRY: dict[str, type] = {}

def component(cls):
    """Register a dataclass as a component type (name = class name, versioned)."""
    cls.__ae_component__ = True
    cls.__ae_version__ = getattr(cls, "__ae_version__", 1)
    _REGISTRY[cls.__name__] = cls
    return cls

def schema() -> dict[str, list[tuple[str, str]]]:
    return {n: [(f.name, str(f.type)) for f in fields(c)] for n, c in _REGISTRY.items()}
```

```python
# engine/world/system.py
class System:
    phase: str = "SIM"            # PRE | SIM | POST | RENDER_SUBMIT
    order: int = 0
    reads: tuple[type, ...] = ()
    writes: tuple[type, ...] = ()
    def run(self, world, ctx, dt: float) -> None: ...
```

```python
# game/missions/m5/systems/guard_render.py
from engine.world import System, Transform, Sprite
from engine.render2d import RotatedSpriteDraw, Layer
from game.missions.m5.components import WalkCycle, HitFlash

class GuardRender(System):
    phase = "RENDER_SUBMIT"
    reads = (Transform, Sprite, WalkCycle, HitFlash)
    def run(self, world, ctx, dt):
        q = ctx.services.render2d.queue
        for eid, (t, s, w, h) in world.query(Transform, Sprite, WalkCycle, HitFlash):
            x, y = t.interp(ctx.clock.alpha)
            sway = w.sway()
            q.submit(RotatedSpriteDraw(s.asset, s.variant, (x + sway.x, y + sway.y), t.angle,
                                       buckets=64), Layer.ENTITIES, sort_key=y)
            if h.active:
                q.submit(h.ring_draw(x, y), Layer.FX_WORLD, sort_key=y)
```

### A.2 Scene
```python
# game/missions/m5/scenes.py
from engine.scene import Scene
from engine.level import load_level
from engine.world import World

class M5PrintWorks(Scene):
    def on_enter(self, ctx):
        self.world = World(ctx.services)
        self.level = load_level("m5/printworks", self.world)
        ctx.services.audio.music.play("m5/printworks_night")
        ctx.input.push_context("gameplay")
        ctx.bus.on("TriggerEntered", self._on_trigger, scope=self)
    def _on_trigger(self, evt):
        if evt.trigger == "maru_office":
            self.stack.push(ctx_cutscene("m5/mid11_maru_two"))
    def fixed_update(self, ctx, dt): self.world.step(ctx, dt)
    def draw(self, ctx, alpha): ctx.services.render2d.render(self.world, self.level, alpha)
```

### A.3 Asset definition (game side)
```python
# game/art/m5/hq_locker.py  (unchanged contract from the M5 prototype)
VARIANTS = 1
VARIANT_NAMES = ("default",)
TEXT_BOXES = ()            # used by asset lint when the sprite draws text
def render(variant=0, scale=1): ...
```

### A.4 Expression evaluator contract
```
expr    := term (('+'|'-') term)*
term    := factor (('*'|'/') factor)*
factor  := NUMBER | NAME | call | '(' expr ')' | '-' factor
call    := NAME '(' [expr (',' expr)*] ')'
NAMES   : t, k, i (repeat index), params.*, pi
CALLS   : lerp(a,b,u), clamp(x,a,b), smoothstep(e0,e1,x), ease_in(u), ease_out(u),
          ease_in_out(u), sin(x), cos(x), min(a,b), max(a,b)
SAFETY  : no attribute access, no indexing, no strings, max depth 32, max 256 tokens
```

---

## Appendix B — Data format examples

### B.1 Timeline (excerpt — `m5/end04_radio`)
```json
{
  "schema": "ae.timeline/1",
  "id": "m5/end04_radio",
  "duration_ms": 8800,
  "letterbox": true,
  "ui_composite": true,
  "layout": {"type": "split", "left": "m5/quay_night", "right": "m5/vasile_office"},
  "params": {"k": {"from_ms": 200, "len_ms": 6000, "ease": "linear"}},
  "tracks": [
    {"type": "camera", "viewport": "right",
     "keys": [{"t": 0, "pos": [0.7, 1.68, -1.5], "target": [-0.05, 1.55, 1.2], "fov": 46},
              {"t": 8800, "pos": [0.7, 1.68, -1.2], "target": [-0.05, 1.55, 1.2], "fov": 40,
               "ease": "linear"}],
     "handheld": {"amp": 0.007, "seed": 10}},
    {"type": "actor", "id": "vasile", "viewport": "right", "cast": "vasile",
     "spawn": {"pos": [0, 0, 1.5], "look_at": [1.2, 0, -3]},
     "keys": [{"t": 0, "pose": "poses/radio_handset", "pose_override": {"head_y": 12}}]},
    {"type": "dialogue", "clips": [{"start": 400, "node": "m5.radio.vasile_01"}]},
    {"type": "event", "markers": [{"t": 8600, "name": "mission_complete"}]}
  ]
}
```

### B.2 Level (excerpt)
```json
{
  "schema": "ae.level/1",
  "id": "m5/printworks",
  "tile_size": 64,
  "size": [24, 20],
  "layers": {
    "floor": {"encoding": "rows", "legend": {"O": "concrete", "P": "lino", "N": "screed"}, "rows": ["..."]},
    "solid": {"encoding": "rows", "legend": {"B": "stack", "H": "wall", "C": "machine"}, "rows": ["..."]}
  },
  "decor": [
    {"asset": "m5/press", "variant": "alarm_if:raid", "tile": [3, 8], "offset": [-18, -6]},
    {"asset": "m5/bale", "variant": "56x56.label", "tile": [15, 17], "inset": 4},
    {"procedural": "leaflets", "rect_tiles": [1.2, 9.5, 14, 1.2], "n": 18, "seed_stream": "decor.printworks"}
  ],
  "spawns": [
    {"prefab": "m5/maru", "tile": [19, 4], "facing": 1.57},
    {"prefab": "m5/guard_raider", "path": "raid_route_a", "stage": "raid"}
  ],
  "triggers": [
    {"id": "maru_office", "rect_tiles": [17, 2, 5, 4], "on_enter": {"timeline": "m5/mid11_maru_two"}}
  ],
  "stages": {
    "printworks": {"objective": "m5.obj.find_maru", "music": "m5/printworks_night"},
    "raid": {"objective": "m5.obj.survive_raid", "timer_s": 70, "hud": ["raid_plate"]}
  }
}
```

### B.3 Dialogue (excerpt)
```json
{
  "schema": "ae.dialogue/1",
  "id": "m5.faces",
  "speakers": {"kovac": {"name": "KOVAC", "color": [232, 132, 60]},
               "biribel": {"name": "BIRIBEL", "color": [230, 230, 230]}},
  "nodes": [
    {"id": "kovac_01", "speaker": "kovac", "text": "m5.faces.kovac_01", "next": "biribel_01"},
    {"id": "biribel_01", "speaker": "biribel", "text": "m5.faces.biribel_01",
     "effects": [{"set": "flags.met_kovac", "value": true}], "next": null}
  ]
}
```

### B.4 Prefab
```json
{
  "schema": "ae.prefab/1",
  "id": "m5/guard_raider",
  "extends": "m5/guard_base",
  "components": {
    "Sprite": {"asset": "m5/m5_guard", "variant": 2},
    "Health": {"max": 70},
    "AIBrain": {"profile": "raider_push"},
    "Tags": {"set": ["guard", "raider"]}
  }
}
```

---

## Appendix C — Checklists

### C.1 Before you commit
- [ ] Smoke test green (full run, not a subset)
- [ ] compileall clean
- [ ] Boundary lint clean (enforce mode once Phase 2 is done)
- [ ] Golden images for the touched areas compared and reviewed
- [ ] Replay segments for the touched missions match
- [ ] Line endings LF, UTF-8, no stray debug prints
- [ ] STATUS / ADAPTERS / CHANGELOG / BUGS updated as needed
- [ ] Task report printed

### C.2 Converting a procedural drawing into an asset
- [ ] Find every call site and its exact pixel origin (offsets, pivots, margins)
- [ ] Write `render(variant, scale)` with deterministic randomness (per-asset seed)
- [ ] Preserve shared RNG consumption at the call site if the original consumed it
- [ ] Declare variants and names; declare text boxes if it draws text
- [ ] Register in the manifest; bake; contact-sheet review (look at it)
- [ ] Wire the call site through the registry with the legacy fallback intact
- [ ] Golden parity (or a deliberate, logged change: e.g. light-direction fixes)
- [ ] Remove the legacy path only after all call sites migrate and parity holds for one full phase

### C.3 Migrating a cutscene take to a timeline
- [ ] Record primitives and parameters at ≥ 30 t values across the take
- [ ] Generate the set3d draft; factor repeats and prop refs
- [ ] Every extracted prop passes the prop quality bar (§6.7): proof sheet, review, budget, footprint, anchors
- [ ] Generate the timeline draft; fit keys; flag dense tracks
- [ ] Golden parity at the baseline t values (25/50/75%) **and** at 5 random t values
- [ ] UI composite check (dialogue box never hides critical information; the N01 lesson)
- [ ] Remove or shrink the imperative take; record it in ADAPTERS.md if partial

### C.4 Adding a subsystem
- [ ] ADR if any design choice is non-obvious
- [ ] Public API in `__init__.__all__`, type hints, docstrings
- [ ] Unit tests and a smoke check
- [ ] Docs page `docs/engine/subsystems/<name>.md` (purpose, API, data, examples, pitfalls)
- [ ] Debug overlay hooks (stats) if the subsystem runs per frame
- [ ] Bench entry if it is on a hot path

---

## Appendix D — Severity scale (shared with the gauntlet)
- **S1:** broken, crashing, illegible, softlocking, or a visible regression from golden. Fix before anything else.
- **S2:** clearly wrong, cheap-looking, inconsistent with the conventions, wrong language, text overflow, placeholder art in a shipped view.
- **S3:** polish (composition nudges, minor repetition, small detail gaps). Logged, batched, and fixed when cheap.

---

## Appendix E — Glossary
- **AE:** Acaristan Engine, everything under `src/engine/`.
- **Adapter:** temporary glue that exposes legacy code through a new engine API. Each one is tracked in ADAPTERS.md with a removal plan.
- **Bake:** deterministic offline render of an asset definition to a file, with a content hash.
- **Golden image:** an approved reference frame for automated visual regression.
- **Gauntlet:** the human-in-the-loop visual QA cycle (render → nitpick → fix → verify → log) with S1–S3 severities.
- **Parity:** identical observable behaviour (pixels within tolerance, state hashes equal) between legacy and migrated code.
- **Strangler migration:** grow the new system around the old one, move callers over and delete the old code last.
- **Set3D:** a declarative 3D environment description, built into engine3d meshes.
- **Timeline:** a declarative cutscene: tracks of keys and clips over time.
- **Static layer:** a pre-baked, chunked world surface for floors and immovable decor.

---

## Appendix F — Phase report template
```
# Phase <n> report — <title>
Date: …   Commits: <range>

## Outcome (first line = honest status)
<DONE | PARTIAL (what is missing) | BLOCKED (by what)>

## Exit criteria
- [x] <criterion> — evidence: <path/log line>
- [ ] <criterion> — gap: <why>, plan: <next step>

## Metrics
- Boundary violations: before → after
- STATE fields: before → after
- Procedural draw calls (census): before → after
- Duplicated UI functions: before → after
- Adapters: added / removed / open
- Bench: <table>

## Visual evidence
- Golden comparisons: <n>, failures <n>, worst <id> (<diff>)
- Images reviewed: <paths>

## Risks & caveats
## Decisions (ADRs)
## Next phase entry check
```

---

## Appendix G — First session script (do exactly this first)
1. Confirm the environment: Python version, pygame-ce version, repo root path, how long the smoke test takes. Run `python tools/smoke_test.py` in the background and wait for `SMOKE TEST: OK`.
2. Create `docs/engine/` with STATUS.md (copy §2 as unchecked boxes and §7 as phase checkboxes), BUGS.md, ADAPTERS.md, CHANGELOG.md, and `adr/ADR-000-template.md`.
3. Write `tools/ae_audit.py`. It produces the import graph, STATE census, cache census, duplication census and file inventory, and writes `docs/engine/AUDIT.md` with tables and counts.
4. Write `tools/ae_golden.py capture --baseline v0`, reusing the gauntlet renderers. Capture cutscene frames at 25/50/75% for every shot, plus all gameplay shots. Verify reproducibility by capturing twice and diffing.
5. Do the line-ending normalisation commit (with tests before and after).
6. Draft ADR-001, ADR-002 and ADR-003.
7. Print the Phase 0 report. Stop for review only if an ADR needs a human decision. Otherwise continue to Phase 1.

---

**Final reminder.** The game you are protecting is good: directed, moody, with careful light. The engine you are building exists so that the *next* five missions can be made faster, safer and more beautifully than the first five. Keep the game playable, keep the frames identical, keep the reports honest, and make every boundary something a tool can check.
