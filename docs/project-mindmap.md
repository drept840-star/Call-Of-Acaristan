---
tags: [project, architecture, reference]
updated: 2026-10-22
source: scripted AST pass over all 372 modules in src/ plus the tools, tests, content and docs trees
---
# Call of Acaristan - project mind map

Top-down action game (Python >=3.13, `pygame-ce`, `numpy`, `moderngl`) on the in-house **RPE6** engine. It has 2D missions M0-M6, a GL/software low-poly 3D renderer for films and the M6 3D fights, and KRAPNET multiplayer.

- Run: `python acaristan.py`
- Gates: `python tools/smoke_test.py` (`SMOKE TEST: OK`), `python -m compileall -q src`, `python tools/ae_ci.py` (`AE CI: OK`)
- Rules: `AGENTS.md`. Engine plan of record: `docs/engine/STATUS.md`. Session handoff: `.wolf/STATUS.md`.

Size map (lines): missions/m3 26.5k, cutscenes 21.7k, ui 18.5k, missions/m2 15.0k, missions/m6 13.3k, missions/m5 7.5k, core 6.9k, entities 5.0k, app.py 4.4k, audio 4.3k, engine3d 3.5k, net 3.4k. The whole `engine/` package is about 9k.

---

## 1. Package dependency graph

Edges come from real imports. The number is the import count, which shows how tightly packages couple.

```mermaid
graph LR
  APP["app.py<br/>main loop"]
  MIS["missions/"]
  CUT["cutscenes/"]
  UI["ui/"]
  CORE["core/"]
  ENT["entities/"]
  FX["fx/"]
  AUD["audio/"]
  NET["net/"]
  GAME["game/"]
  ART["art/ shim"]
  E3D["engine3d/"]
  ENG["engine/*"]

  APP -->|45| MIS
  APP -->|30| CORE
  APP -->|13| UI
  APP --> AUD
  APP --> GAME
  APP --> CUT

  MIS -->|249| CORE
  MIS -->|160| ENT
  MIS -->|82| UI
  MIS -->|50| NET
  MIS -->|45| GAME
  MIS -->|36| CUT
  MIS -->|35| E3D
  MIS -->|24| FX
  MIS -->|12| AUD
  MIS -->|12| ART
  MIS -->|~95| ENG

  CUT -->|105| E3D
  CUT -->|56| CORE
  CUT -->|16| ENG
  CUT --> GAME

  UI -->|53| CORE
  UI -->|27| ENG
  UI -->|8| NET
  UI --> FX
  UI --> ENT

  GAME -->|40| MIS
  GAME -->|32| CORE
  GAME --> ENG
  GAME --> E3D

  CORE -->|11| MIS
  CORE -->|23| ENG
  CORE --> GAME
  CORE --> ENT
  CORE --> AUD
  CORE --> NET

  ENT -->|20| CORE
  ENT -->|14| ENG
  ENT --> FX
  FX --> CORE
  AUD --> CORE
```

Reading it:
- `core/` is the hub. Almost everything reads `core.state.STATE` and `core.config`.
- `missions/` is the heaviest consumer: it pulls entities, UI widgets, net (the arena) and game adapters.
- `cutscenes/` is mainly a client of `engine3d/`, with 105 imports.
- The `game` and `missions` packages, and `core` and `missions`, import each other. Those links are lazy, function-level imports (`# lazy:`), so they don't form cycles at load time.
- `engine/*` never imports the game. It is the clean layer.

---

## 2. Boot and frame flow

```mermaid
graph TD
  L["acaristan.py<br/>sys.path += src, import app"] --> A["src/app.py runs on import"]
  A --> SET["core.settings_store + core.user_settings<br/>settings.json"]
  A --> SAVE["core.save_system<br/>save_data.json, 3 slots"]
  A --> PROF["core.profile_store<br/>Acaribucks, cosmetics"]
  A --> INP["game.input_adapter<br/>bindings, gamepad"]
  A --> FSM["core.fsm.GameStateManager<br/>mirrored by core.scene_mirror onto engine.scene.SceneStack"]

  FSM --> MENU["ui.main / ui.system<br/>menu, settings, pause, death"]
  FSM --> MSN["core.game_core facade<br/>start_mission*, dispatch"]
  FSM --> CS["app.CutscenePlayer / start_cutscene<br/>2D or 3D shot lists"]
  FSM --> MP["ui.mp, ui.match_screen, ui.shop<br/>KRAPNET + arena"]

  MSN --> UPD["missions.mX game_update<br/>fixed step via core.fixedstep"]
  MSN --> DRW["missions.mX game_draw"]
  UPD --> ENTS["entities: Player, Enemy, weapons, corpses"]
  UPD --> INT["core.interactions: doors, safe, NPCs, alarms"]
  UPD --> AUDM["audio.audio.AudioManager + audio.voice"]
  DRW --> RQ["game.render RenderHost<br/>engine.render2d queue + static layers + lighting"]
  DRW --> HUD["ui.hud + engine.ui.std widgets"]
  CS --> E3["engine3d.Renderer<br/>GL FBO or software painter"]
  E3 -->|readback| SURF["pygame Surface"]
  RQ --> SURF
  HUD --> SURF
  SURF --> PRES["app._present_frame<br/>grain, postprocess, display mode"]
  PRES --> WIN["pygame window, never pygame.OPENGL"]
  MSN -->|mission end| REP["app._mission_report_data<br/>ui.mission_failed on fail"]
```

---

## 3. RPE6 engine (`src/engine/`)

```mermaid
mindmap
  root((engine RPE6))
    core
      clock - fixed-step Clock
      timebase - now_ms now_s pin_wall
      rng - named seeded streams
      events - typed EventBus
      services - service registry
      config - layered Settings
      log, errors, profiling, mathx
      app - App boot run shutdown
    scene
      scene - Scene lifecycle
      stack - SceneStack
      cutscene - CutsceneScene timed shots
      inspect - InspectScene first-person look
    world ECS-lite
      entity - World EntityId
      _component - component schema
      std - Transform Velocity Collider Health
      system - System Scheduler
      prefab - PrefabLibrary
    render2d
      queue - RenderQueue layers
      drawables - Sprite Surface Batch draws
      camera - Camera2D shake lookahead
      static - StaticLayers chunk bakes
      postfx - vignette grain grade letterbox
      pen - SurfacePen RecordingPen
      util - screen_visible soft_shadow
    render3d
      scene3d - declarative set3d
      presets - lighting moods
    lighting
      buffer - half-res LightBuffer
      lightmap - multiplicative LightMap
    ai
      bt - behaviour trees
      senses - Sight NoiseBus memory
      cover - cover spots peek
      squad - shared group state
    collision
      boxes - BoxWorld ray AABB
      nav - GridNav A star
    assets
      registry - AssetRegistry fallbacks reload
      _artpack - sprite registry
      loaders - only raw file loads
      bake, layerbake, manifest, watch
    data models
      timeline - model player expr
      dialogue - model runner
      level - model tiled importer
      save - snapshot statehash
      settings - typed fields
      input - ActionMap
      text - strings T fonts layout
    ui
      theme
      std widgets - minimap health_bar crosshair dialogue_box objective_banner prompt weapon_panel hostiles bottle_hud
    anim
      figure_kit - 2D cast renderer
      pose_cache
```

---

## 4. Game glue (`src/game/`), core services (`src/core/`), 3D renderer (`src/engine3d/`)

```mermaid
graph TD
  subgraph game["game/ - engine-to-content adapters"]
    GR["render/ RenderHost, adapters"]
    GW["world/ World + Scheduler<br/>legacy.py strangler views"]
    GB["render3d_bridge<br/>set3d, mesh, texture loading"]
    GS["save_adapter capture restore statehash"]
    GD["dialogues / timelines / levels<br/>use_legacy switch"]
    GI["input_adapter"]
    GDEV["devtools in-game debug"]
    GA["art/m1..m5 procedural sprite painters"]
    GC[("content/ JSON data")]
  end
  subgraph core["core/ - shared game services"]
    ST["state.STATE singleton"]
    CFG["config colours, HEIGHT, grain, skyline painters"]
    GCORE["game_core mission start facade"]
    MB["mapbuilder MapBuilder, no deps"]
    CAM["camera follow, lookahead, bullets"]
    INTR["interactions doors safe NPCs"]
    APPR["appearance + outfits + profile_store"]
    SAVES["save_system settings_store json_store"]
    FIX["fixedstep FixedStepClock"]
    MISC["ambience surfaces props hands staticlayer console dev_jumps mission_meta cutscene_registry"]
  end
  subgraph e3d["engine3d/"]
    R["Renderer picks GL or software"]
    GL["gl.py GLRenderer ModernGL FBO"]
    SW["core.py math meshes camera SoftwareRenderer"]
    RIG["rig.py Humanoid boxes on joints, poses"]
    IK["ik.py two-bone arm leg rifle hold"]
    TX["textures.py pixel textures, glitter"]
  end
  GD --> GC
  GB --> GC
  GB --> R
  R --> GL
  R --> SW
  RIG --> R
  IK --> RIG
  TX --> R
  GW --> ST
  GCORE --> ST
```

Content data (`src/game/content/`):
- `levels/*.level.json` - m1 warehouse, m2 city, m3 archives/broadcast/cell/comms/kill_order, m4 station/street, m5 hq/print/quarter.
- `timelines/*.timeline.json` - cutscene shot lists (core, m2, m3, ...).
- `dialogue/*.dlg.json` - m4 liaison, m5 maru, mission0 briefing.
- `sets/*.set3d.json`, `meshes/*.mesh.json`, `textures/*.texture.json`, `lighting3d/*.preset.json`, `grades/*.grade.json`.
- `strings/en.json` - every UI/caption string, looked up with `engine.text.T()`.
- `m1..m5/manifest.json` - art pack manifests; `m5/palette.json`.

---

## 5. Missions (`src/missions/`)

Each mission is a package whose `__init__.py` is a re-export facade; facade order is load order. Common parts: `meta` (constants and timelines), `maps` (MapBuilder to `list[str]`), `world` (spawns, NPCs), `flow` (start and checkpoints), `systems`/`update` (per-frame), `draw` (renderer), `components` (ECS roles).

```mermaid
mindmap
  root((missions))
    m0 Depot
      __init__ - generated thin host, briefing, outro
    m1 Warehouse escape
      map, main start_mission, update, draw
      hotwire - car hotwire minigame
    m2 Route 12
      meta zones, world, starts, update, draw 8k lines
      sniper - 2D sniper ambush, Seby OS-12
      sniper3d + sniper3d_set - 3D Kill-Box film
    m3 Kill Order
      __init__ 6.6k - facade plus check harness
      meta, maps, world, flow
      systems 4.2k - game_update, K-9, crafting
      draw 8.2k - archives, Vostral pickup cinematics
      interrog - interrogation
      sweep - Kill Order sweep director, overwatch laser
    m4 Aftermath
      meta, maps zones, world, flow, systems, draw
    m5 Martial Law
      meta, maps, world, flow, systems, draw, render
      decor, decor_paint, decor_interior - set dressing
      quarter - Lower Quarter systems
      tram_wreck, water - burning tram, floodwater
      inspect_fpv, inspect_art, inspect_art_street - E look shots
      finale_script, finale_audio
    m6 Black Notebook
      meta, maps, world, flow, systems, draw, decor
      stealth - floodlight stealth
      train3d 5.2k - interactive 3D train TrainScene
      yard3d - Who fired 3D fight YardScene
      yard_brain - Guard brains on engine.ai
      yard_dress, yard_hud, hud3d, palette3d
      bloc3d - blocks stacks tower signs font colours
      m6_audio - film stems, train bed
    shared
      walking_sim 3.1k - slum walk, NPCs, overlook
      walking_attack3d - 3D oil-rig strike
      arena 1.6k - MP maps, deathmatch rules, payouts
```

### M6 detail (current branch `m6/train-polish`)

```mermaid
graph TD
  F["m6/flow.py<br/>stage ladder, checkpoints, ending handoff"] --> TOP["2D stages: customs, no-man's-land, rail yard<br/>maps.py + world.py + systems.py + draw.py + decor.py + stealth.py"]
  F --> FILMS["cutscenes/m6films.py<br/>every M6 film, 3D take + 2D fallback"]
  F --> TRAIN["m6/train3d.py TrainScene<br/>interactive 3D train shootout"]
  F --> YARD["m6/yard3d.py YardScene<br/>third-person fight after Volkov dies"]
  FILMS --> W3D["cutscenes/m6world3d.py sets, actor kit, pack_memo"]
  FILMS --> FX3D["cutscenes/m6fx3d.py PS2 night light, halos, haze"]
  TRAIN --> HUD3D["m6/hud3d.py"]
  TRAIN --> AUD6["m6/m6_audio.py M6TrainAudio, M6FilmAudio"]
  YARD --> BRAIN["m6/yard_brain.py Brain on engine.ai bt/senses/cover/squad"]
  YARD --> DRESS["m6/yard_dress.py + bloc3d/*"]
  YARD --> YHUD["m6/yard_hud.py 2D HUD in 3D"]
  W3D --> E3D["engine3d Renderer, rig, ik, textures"]
  TRAIN --> E3D
  YARD --> E3D
  BRAIN --> COLL["engine.collision BoxWorld, GridNav"]
  PAL["m6/palette3d.py 2D palette for 3D"] --> TRAIN
  PAL --> YARD
  SHOTS["tools/m6_shots.py, tools/m6_halo_sheet.py"] -.renders.-> FILMS
```

---

## 6. Cutscenes (`src/cutscenes/`)

```mermaid
graph LR
  REG["core.cutscene_registry<br/>scene id to renderer"] --> ENG2D["cutscenes/engine.py<br/>draw_cutscene_scene, typewriter, dialogue slide"]
  ENG2D --> C2D["2D sets: chair, route12, m3cell, m3ops, m3ko, m3broadcast, m3ending, m4aftermath, m5martial, k9"]
  C2D --> CAST["cast.py + engine.anim.figure_kit"]
  REG --> C3D["3D sets: m5martial3d, m5mid3d, m5shadow3d, m5ending3d, m6films, oil_rig_3d"]
  C3D --> CAST3D["cast3d.py: SPECS to engine3d Humanoid"]
  C3D --> KITS["fx kits: m5fx3d, m6fx3d, weather3d, m5decal, m5harbour_art, m5studio, m6world3d"]
  C3D --> POST["post3d.py: grade + grain"]
  CAST3D --> E3D["engine3d"]
  KITS --> E3D
  TL[("content/timelines")] --> REG
```

The cast look is defined once in `figure_kit.SPECS`. The 2D cutscenes, the 3D rigs (`cast3d`) and the radio portraits (`tools/sprites/portraits.py`) all derive from it.

---

## 7. UI, audio, net, entities

```mermaid
mindmap
  root((front end and actors))
    ui
      main - menu, cursor, keydown
      system - settings, pause, death screen
      widgets - ModernButton, hover, clipboard
      hud - minimap, safe keypad, notebook, desk notes
      radio + pixfont - radio widget, bitmap fonts R7 R5
      mission_failed - failure terminals
      upload_os - CRT terminal OS for evidence upload
      mp + multiplayer_style - server browser, DMs
      match_screen + arena_view - live arena match
      shop - Outfitter, Acaribucks
    audio
      audio - AudioManager music SFX ambience
      voice - VO playback find_line play_line
      voice_manifest - VO_xxx rows, KNOWN_MISSING_AUDIO
    net KRAPNET
      protocol - wire format
      client - MPRelayClient
      match - MatchSession host + clients
      discovery - LAN master
      portmap - UPnP NAT-PMP
      roomcode, tcp_tunnel - bore tunnels
    entities
      player - Player movement, melee
      enemy_ai - Enemy, hear shot
      weapons - pistol, melee, molotov, FireZone
      weapon_rig - OS-12, K-9, pistol draw
      corpse, fallen, death_anim
      adornments - head gear registry
      art_cache - procedural surface cache
    fx
      effects - particles, casings, blood decals
```

---

## 8. Asset and verification pipeline

```mermaid
graph TD
  SPG["tools/sprites/*.py<br/>vehicles props fx portraits mission_failed<br/>palette.py + kit.py"] -->|build_all_sprites.py, deterministic| SHEETS[("assets/art spr_*.png + .json")]
  GART["game/art/m1..m5 painters"] -->|bake_m5_sprites, ae_bake| BAKED[("assets/baked")]
  SHEETS --> AP["engine.assets._artpack via core.artpack<br/>procedural fallback always kept"]
  BAKED --> AP
  T3D[("assets/tex3d, assets/3D, content/meshes")] --> BR["game.render3d_bridge"]
  VO[("assets/voice + voice_lines.xlsx")] --> VM["audio/voice_manifest.py"]
  MUS[("assets/music, *.mp3, sfx_wav/")] --> AM["audio.AudioManager"]

  SMOKE["tools/smoke_test.py"] --> CI["tools/ae_ci.py full gate"]
  CI --> CHK["ae_*_check: dialogue level set3d timeline text import reexport"]
  CI --> GOLD["ae_golden.py + tests/golden"]
  CI --> REPL["ae_replay*.py + tests/replay, tests/loop"]
  CI --> UNIT["tests/unit 49 files"]
  CI --> API["ae_api_snapshot + tests/api/engine_api.json"]
  CI --> NORM["ae_normalize LF UTF-8"]
  E3C["tools/engine3d_check.py GL vs software parity"] --> CI
```

---

## Where to find X

| Need | Go to |
|---|---|
| Main loop, state transitions, cutscene start | `src/app.py` (`trigger_transition`, `start_cutscene`, `_present_frame`) |
| Global game state | `src/core/state.py` (`STATE`) |
| Colours, screen size, sky/building painters | `src/core/config.py` |
| Start a mission or checkpoint | `src/core/game_core.py`, then `missions/mX/flow.py` or `starts.py`/`main.py` |
| Dev jump targets (`--dev-mission6-shootout` and others) | `src/core/dev_jumps.py` |
| Mission name, radio channel, fail text | `src/core/mission_meta.py`, `missions/mX/meta.py` |
| Map layout | `missions/mX/map.py` or `maps.py` (MapBuilder), `content/levels/*.level.json` |
| Enemy behaviour (2D) | `src/entities/enemy_ai.py`; M3 sweep `missions/m3/sweep.py` |
| Enemy brains (3D yard) | `missions/m6/yard_brain.py` on `engine/ai/` |
| Player movement and weapons | `entities/player.py`, `entities/weapons.py`, `entities/weapon_rig.py` |
| Doors, safe, NPC interactions | `src/core/interactions.py` |
| HUD | `ui/hud.py`, `engine/ui/std/*`; 3D HUDs `missions/m6/hud3d.py`, `yard_hud.py` |
| Menus, settings, pause | `ui/main.py`, `ui/system.py` |
| Radio calls | `ui/radio.py`, `ui/pixfont.py` |
| Any UI string or caption | `src/game/content/strings/en.json` |
| Voice line ids | `src/audio/voice_manifest.py`; playback `audio/voice.py` |
| Music, SFX, ambience | `audio/audio.py`, `core/ambience.py`, `core/surfaces.py` (footsteps) |
| Mission-specific audio | `missions/m5/finale_audio.py`, `missions/m6/m6_audio.py` |
| 3D renderer API | `engine3d/core.py` (software + math), `engine3d/gl.py` (GL) |
| 3D characters and poses | `engine3d/rig.py`, `engine3d/ik.py`, `cutscenes/cast3d.py` |
| 2D character look | `engine/anim/figure_kit.py` (`SPECS`), `cutscenes/cast.py` |
| A cutscene's shots | `content/timelines/*.timeline.json`, or the `meta.py` timelines of M5/M6 |
| A cutscene's drawing | `cutscenes/<mission file>.py` (see section 6) |
| Post grade and grain | `cutscenes/post3d.py`, `engine/render2d/postfx.py`, `content/grades/` |
| Sprites | `tools/sprites/*` generate them, `assets/art/` holds them, `core.artpack` reads them |
| Saves | `core/save_system.py`, `core/json_store.py`, `game/save_adapter.py` |
| Settings | `core/settings_store.py`, `core/user_settings.py`, `engine/settings/` |
| Key bindings | `game/input_adapter.py`, `engine/input/model.py` |
| Multiplayer | `net/*`, `ui/mp.py`, `ui/match_screen.py`, `ui/arena_view.py`, `missions/arena.py` |
| Collision and pathing | `engine/collision/boxes.py`, `engine/collision/nav.py` (roadmap 6.9) |
| Engine design and bugs | `docs/engine/ARCHITECTURE.md`, `STATUS.md`, `BUGS.md`, `ADAPTERS.md`, `adr/` |
| Story canon | `docs/LORE.md`, `docs/MISSION*_PLOT.md`, `docs/FIXES_STORIES.md` |
| History | `docs/worklog.md`, `docs/engine/CHANGELOG.md` |
| Shot evidence and renders | `shots/`, `tools/m5_shots.py`, `tools/m6_shots.py` |

---

## Key directories

- `src/` - all game code (section 1). It is added to `sys.path` by the launcher.
- `assets/` - runtime media: `art/` generated sheets, `baked/` layers, `tex3d/` and `3D/` textures and meshes, `music/`, `voice/`, `fonts/`, `sprites/`.
- `tools/` - gates (`smoke_test.py`, `ae_ci.py`, `ae_*`), sprite generators (`sprites/`), mission shot and probe scripts (`m5_*`, `m6_*`), trailer renderers, MP host/join bots, build scripts (`build_windows.py`, `build_*_exe.bat`).
- `tests/` - `unit/` (49 test files), `golden/` and `replay/`/`loop/` baselines, `api/engine_api.json` snapshot, `data/` scene traces.
- `docs/` - lore, mission plots and plans, audits (`AUDIT_T1..T8`), `worklog.md`, and `engine/` (architecture, ADRs, bugs, status).
- `shots/`, `_shots/`, `previews/`, `outputs/`, `trailers/`, `validation/` - generated evidence and renders. They are not code.
- `archive/`, `handoff/`, `SKILLS/`, `apollo-agent/` - old material and agent tooling.
- `.wolf/` - OpenWolf: `STATUS.md` handoff, `anatomy.md` file index, `buglog.json`, `cerebrum.md`.

## Critical files

- Entry: `acaristan.py`, `src/app.py`
- State and flow: `src/core/state.py`, `src/core/fsm.py`, `src/core/scene_mirror.py`, `src/engine/scene/stack.py`, `src/core/game_core.py`
- Time: `src/engine/core/timebase.py`, `src/core/fixedstep.py`
- Maps: `src/core/mapbuilder.py`
- Render: `src/game/render/host.py`, `src/engine/render2d/queue.py`, `src/engine3d/gl.py`, `src/engine3d/core.py`
- Data: `src/game/content/strings/en.json`, `src/audio/voice_manifest.py`
- Config and build: `pyproject.toml`, `Call of Acaristan.spec`, `build.bat`, `.gitattributes`
- Rules: `AGENTS.md`, `CLAUDE.md`, `docs/engine/STATUS.md`

## Architectural patterns

- **Facade packages.** Package `__init__.py` files re-export their part modules, and facade order is load order. Parts import only earlier parts at top level; later ones go in lazy `# lazy:` imports.
- **Single-owner mutable globals.** Read them as `import owner as _o; _o.name`, never `from owner import name`. Facades expose them as PEP 562 live views.
- **Strangler migration to RPE6.** Legacy objects are mirrored into the engine (`core/scene_mirror.py`, `game/world/legacy.py`, `game/*` `use_legacy` switches). Deprecated `core.artpack`, `core.lighting` and `entities.sprite_lib` paths forward into `engine.*`.
- **Game time only.** Use `engine.core.now_ms()/now_s()`. Never call `pygame.time.get_ticks()` or `time.time()` in gameplay or draw code.
- **Maps stay `list[str]`.** Structure and spawns are authored separately and baked; collision, minimap, camera and A* depend on that format.
- **3D on a 2D window.** `engine3d` draws off-screen and the frame is read back onto the pygame Surface. GL falls back to software (`ACARISTAN_RENDERER=gl|software`).
- **Code-generated deterministic art.** Sprites come from seeded generators and are read through `core.artpack`, always with a procedural fallback.
- **Data-driven content.** Levels, timelines, dialogue, 3D sets, presets and strings are JSON under `game/content`, validated by `tools/ae_*_check.py`.
- **Voice lines.** A new line needs a `VO_xxx` row plus a `KNOWN_MISSING_AUDIO` entry, never a `VOICE_ORDER` entry. Never edit a line that already has a recorded take.

Hot spots to read with ranges, not whole: `missions/m3/draw.py` (8.2k lines), `missions/m2/draw.py` (8.0k), `missions/m3/__init__.py` (6.7k), `missions/m6/train3d.py` (5.2k), `app.py` (4.4k), `missions/m3/systems.py` (4.2k), `ui/match_screen.py` (3.7k), `ui/mp.py` (3.4k), `audio/audio.py` (3.2k), `missions/walking_sim.py` (3.1k), `ui/upload_os.py` (3.1k).
