# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-10-22T18:35:59.987Z
> Files: 429 tracked | Anatomy hits: 0 | Misses: 0

> Project structure index. Auto-maintained by OpenWolf hooks and daemon.
> Run `openwolf scan` to generate, or wait for the first Claude Code session.
> Status: Pending initial scan

## ./

- `.gitattributes` — Git attributes (~97 tok)
- `.gitignore` — Git ignore rules (~763 tok)
- `acaristan.py` — Thin launcher — run with `python acaristan.py` from the repo root. (~106 tok)
- `AGENTS.md` — Agent workflow (read this first) (~2517 tok)
- `build.bat` (~56 tok)
- `CLAUDE.md` — OpenWolf (~337 tok)
- `GEMINI.md` — OpenWolf (~75 tok)
- `HANDOFF_CLAUDE.md` — Handoff — Claude (~1583 tok)
- `MEMORY.md` — RULE: Split long tasks into Planning and Writing stages (~554 tok)
- `pyproject.toml` — Python project configuration (~53 tok)
- `README.md` — Project documentation (~286 tok)

## .claude/

- `launch.json` (~97 tok)

## docs/

- `M6_HALOS_AND_ENDING_PLAN.md` — M6 plan - halos that stay behind walls, and an ending the player can follow (~5753 tok)
- `project-mindmap.md` — Call of Acaristan - project mind map (~5316 tok)

## src/

- `app.py` — _input_recorder: handle_settings_event (~55737 tok)

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
- `m6films.py` — m6films.py - engine3d takes and 2D fallbacks for every Mission 6 film. (~31211 tok)
- `m6fx3d.py` — m6fx3d.py - the Mission 6 FX kit: m5fx3d with hard PS2 halos. (~2184 tok)
- `m6world3d.py` — m6world3d.py - engine3d sets and actor kit for the Mission 6 films. (~28902 tok)
- `oil_rig_3d.py` — True-3D Oil Rig Bombing cutscene (engine3d). Timeline-driven; VO gates shots. (~1907 tok)
- `post3d.py` — Cinematic post stack for cutscene shots (RPE6 Phase 11 step 5). (~1722 tok)
- `route12.py` — Split from cutscenes.py - see cutscenes.py (shim) for the map. (~22720 tok)
- `weather3d.py` — Data-driven weather & atmosphere for 3D sets (RPE6 Phase 11 step 6). (~1610 tok)

## src/engine/

- `__init__.py` — Retardovici Pulse Engine 6 Gold (RPE6): the Call of Acaristan engine. (~88 tok)

## src/engine/ai/

- `__init__.py` — engine.ai - enemy brains: behaviour trees, senses, squads and cover. (~182 tok)
- `bt.py` — engine.ai.bt - a small behaviour tree runtime. (~2447 tok)
- `cover.py` — engine.ai.cover - cover spots around solid boxes, and picking one. (~1710 tok)
- `senses.py` — engine.ai.senses - what an agent knows about its target. (~1488 tok)
- `squad.py` — engine.ai.squad - what a group of agents shares. (~1096 tok)

## src/engine/anim/

- `__init__.py` — engine.anim - animation (RPE6). Phase 2 holds the generic 2D figure kit (``draw_character`` and the (~252 tok)
- `figure_kit.py` — figure_kit.py - one cast renderer in the "Balaceanu Arrest" house style. (~10926 tok)
- `pose_cache.py` — Pose cache: render-once surfaces for parameterised procedural bodies. (~414 tok)

## src/engine/collision/

- `__init__.py` — engine.collision - solid-world queries for gameplay (RPE6 §6.9). (~154 tok)
- `boxes.py` — engine.collision.boxes - ray, segment and body queries against AABBs. (~1256 tok)
- `nav.py` — engine.collision.nav - A* on a walkability grid (RPE6 §6.9 ``GridGraph``). (~2219 tok)

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

- `__init__.py` — engine3d - tiny flat-shaded low-poly software renderer for pygame. (~212 tok)
- `core.py` — Core of the low-poly renderer: math, meshes, camera, painter renderer. (~10156 tok)
- `gl.py` — engine3d.gl - GPU backend for the low-poly renderer (ModernGL). (~12471 tok)
- `ik.py` — Analytic two-bone IK for the box rig (engine3d.rig.Humanoid). (~3209 tok)
- `rig.py` — Low-poly humanoid rig: boxes on a joint hierarchy, posed by angle dicts. (~15952 tok)
- `textures.py` — engine3d.textures - pixel textures on world faces. (~1502 tok)

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
- `palette3d.py` — The 2D top-down M6 palette, for the 3D yard and train. (~463 tok)
- `stealth.py` — Mission 6 - floodlight stealth for no-man's-land and the rail yard. (~3989 tok)
- `systems.py` — Mission 6 - per-frame gameplay pipeline. (~2860 tok)
- `train3d.py` — Mission 6 - the interactive 3D train scene (``docs/MISSION6_PLOT.md``). (~67119 tok)
- `world.py` — Mission 6 - world construction, Guard spawns and shared helpers. (~3755 tok)
- `yard_brain.py` — Mission 6 yard - the Guard brains (engine.ai on the "Who fired?" fight). (~6394 tok)
- `yard_dress.py` — Mission 6 yard - the clutter that makes the walled yard look lived in. (~3450 tok)
- `yard_hud.py` — Mission 6 yard - the 2D top-down game's HUD, brought into the 3D fight. (~2128 tok)
- `yard3d.py` — Mission 6 - "Who fired?": the third-person fight after Volkov's death. (~23145 tok)

## src/missions/m6/bloc3d/

- `__init__.py` — bloc3d - the Bloc around the M6 yard and station, built from boxes. (~255 tok)
- `blocks.py` — Prefab Soviet panel blocks for the Bloc district. (~1833 tok)
- `colours.py` — Phase-5 colours for the Bloc landmarks and signage. (~436 tok)
- `font.py` — A 5x7 pixel font for the Cyrillic signage on the Bloc. (~1586 tok)
- `signs.py` — Cyrillic signage for the Bloc: rooftop letters, boards, stars, billboards, banners. (~2069 tok)
- `stacks.py` — Industrial silhouettes on the skyline: chimneys, a radio mast, a water tower. (~1515 tok)
- `tower.py` — Watchtowers and wire fences for the Bloc yards. (~1758 tok)

## src/net/

- `__init__.py` — net - multiplayer relay client. Parts: protocol.py, client.py. (~285 tok)
- `client.py` — Game-side client for the KRAPNET master server. (~4646 tok)
- `discovery.py` — LAN auto-discovery for the master server. (~511 tok)
- `match.py` — A multiplayer match session: authoritative host + interpolating clients. (~4524 tok)
- `portmap.py` — Automatic router port forwarding (UPnP IGD + NAT-PMP), stdlib only. (~7430 tok)
- `protocol.py` — Wire protocol for the Acaristan multiplayer master server. (~14266 tok)
- `roomcode.py` — Short, game-branded room codes for direct arena matches. (~1552 tok)
- `tcp_tunnel.py` — Public raw-TCP tunnels for arena matches. (~2992 tok)

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

## tests/unit/

- `__init__.py` (~0 tok)
- `_helpers.py` — Shared test setup: put ``src`` on sys.path and keep SDL headless. (~194 tok)
- `_path.py` (~51 tok)
- `test_anim_props.py` — Phase 11 step 10: flicker is a deterministic closed form; set fields (~705 tok)
- `test_app_boot_crash.py` — engine.core.App: headless boot, service wiring, crash report (§6.1 acceptance). (~1464 tok)
- `test_art_cache.py` — art_cache.get_plate_bg: the shared M4/M5 "status plate" chrome. (~469 tok)
- `test_assets_registry.py` — engine.assets Phase 3: manifest schema, registry chain + cache + ref-counts, bake/check (~5220 tok)
- `test_bloc3d.py` — Phase 5: the Bloc landmarks and Cyrillic signage build sane boxes. (~1810 tok)
- `test_cast_shadows.py` — Phase 11 step 7 (ADR-023): baked cast shadows - occluded faces darken, (~619 tok)
- `test_clock.py` — engine.core.Clock: fixed-step semantics, identity with the legacy FixedStepClock (ADR-004). (~1940 tok)
- `test_devtools.py` — RPE6 Phase 10 (§6.19): debug overlay / inspector data builders + console commands. (~1005 tok)
- `test_engine_ai.py` — engine.ai: behaviour tree preemption and memory, sight reaction and (~3255 tok)
- `test_engine_boot.py` — App.boot display ownership (ADAPTER A-001). (~626 tok)
- `test_engine_collision.py` — engine.collision: box rays and segments agree with brute force, and grid (~1776 tok)
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
- `test_ik.py` — engine3d.ik: analytic arm/leg IK and the shouldered rifle hold land on (~1570 tok)
- `test_m5_ending.py` — M5 finale regressions. Run: python -m unittest tests.unit.test_m5_ending -v. (~2231 tok)
- `test_m5_finale_audio.py` — Focused M5 sound/lifecycle regressions, without starting app or saves. (~3099 tok)
- `test_m6_campaign.py` — Mission 6 campaign regressions. Run: python -m unittest tests.unit.test_m6_campaign -v. (~13379 tok)
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

- `dev_panel.py` — dev_panel.py - clickable dev control panel for jumping into missions. (~7838 tok)
- `m6_shots.py` — M6 3D film + interactive train stills. (~4802 tok)
- `smoke_test.py` — Must be set before pygame/config import. (~126097 tok)
