# FILE INDEX

Generated appendix of `docs/ARCHITECTURE_MAP.md` (`tools/sync_arch_map.py`). Section numbers match the main map so cross-references stay valid. Regenerate with `python tools/sync_arch_map.py`.

## 12.1 Dev jump targets (auto)

From `core/dev_jumps.DEV_JUMPS`; use as `--jump <target>` or the listed flag.

<!-- AUTO:devjumps -->
| target | flag | what |
|---|---|---|
| `m0` | `--dev-mission0` | Mission 0 - Depot (tutorial mission, playable) |
| `m1` | `--dev-m1` | Mission 1 opening handoff (dropoff radio cut, then playable) |
| `m1-game` | `--dev-m1-game` | Mission 1 warehouse from the start (playable, no cutscene) |
| `m1-safe` | `--dev-safe` | Mission 1 at the notebook safe keypad (code 742) |
| `walk` | `--dev-walk` | Walking sim harbor exploration from the start |
| `walk-after` | `--dev-walk-after` | Walking sim harbor right after the rig-strike cutscene (van ready) |
| `m2` | `--dev-mission2` | Mission 2 intro cutscene |
| `m2-game` | `--dev-mission2-game` | Mission 2 gameplay from the start |
| `m2-sniper` | `--dev-mission2-sniper` | Mission 2 Route 12 sniper ambush |
| `m2-after-sniper` | `--dev-mission2-after-sniper` | Mission 2 right after the sniper fight |
| `m2-flank` | `--dev-mission2-flank` | Mission 2 flank cutscene / phase |
| `m2-truck` | `--dev-mission2-truck` | Mission 2 truck stage |
| `m2-evidence` | `--dev-mission2-evidence` | Mission 2 evidence-completion cinematic |
| `m3` | `--dev-mission3` | Mission 3 intro cutscene |
| `m3-game` | `--dev-mission3-game` | Mission 3 breakout gameplay (post-breach, chair leg) |
| `m3-comms` | `--dev-mission3-comms` | Mission 3 comms wing (via service transition cutscene) |
| `m3-archives` | `--dev-mission3-archives` | Mission 3 archives wing checkpoint |
| `m3-kill-order` | `--dev-mission3-kill-order` | Mission 3 kill-order ground floor (+ KO intro cutscene) |
| `m3-ledger` | `--dev-mission3-ledger` | Mission 3 black ledger debug |
| `m3-vostral` | `--dev-mission3-vostral-cutscene` | Mission 3 Vostral acquisition cinematic |
| `m3-archives-cutscene` | `--dev-mission3-archives-cutscene` | Mission 3 comms-to-archives transition cutscene |
| `m3-broadcast-transition` | `--dev-mission3-broadcast-transition` | Mission 3 kill-order-to-broadcast transition cutscene |
| `m3-broadcast` | `--dev-mission3-broadcast` | Mission 3 broadcast wing checkpoint (Slice 6 gauntlet) |
| `m3-upload` | `--dev-mission3-upload` | Mission 3 at the station PC, upload OS already open |
| `m4` | `--dev-mission4` | Mission 4 intro cutscene |
| `m4-game` | `--dev-mission4-game` | Mission 4 aftermath street gameplay from the start |
| `m4-station` | `--dev-mission4-station` | Mission 4 radio-station interior checkpoint |
| `m4-tower` | `--dev-mission4-tower` | Mission 4 transmitter hold (siege checkpoint) |
| `m5` | `--dev-mission5` | Mission 5 intro bulletin cutscene |
| `m5-hq` | `--dev-mission5-hq` | Mission 5 Guard HQ walking sim (Vasile's office) |
| `m5-game` | `--dev-mission5-game` | Mission 5 Lower Quarter gameplay (HQ skipped) |
| `m5-printworks` | `--dev-mission5-printworks` | Mission 5 MAG print works (find Maru, then the raid) |
| `m5-tunnel` | `--dev-mission5-tunnel` | Mission 5 basement tunnel escort (deepest resume point) |
| `m5-ending` | `--dev-mission5-ending` | Mission 5 final cutscene (shadow finale at the river) |
| `m6` | `--dev-mission6` | Mission 6 intro cutscene |
| `m6-game` | `--dev-mission6-game` | Mission 6 top-down gameplay from customs (no intro) |
| `m6-crossing` | `--dev-mission6-crossing` | Mission 6 top-down no-man's-land crossing |
| `m6-rail` | `--dev-mission6-rail` | Mission 6 top-down rail yard |
| `m6-boxcar` | `--dev-mission6-boxcar` | Mission 6 rail yard at Volkov's boxcar (E starts the 3D talk) |
| `m6-train` | `--dev-mission6-train` | Mission 6 train checkpoint |
| `m6-3d` | `--dev-mission6-3d` | Mission 6 interactive 3D train scene (shootout) |
| `m6-shootout` | `--dev-mission6-shootout` | Mission 6 interactive 3D train scene (shootout) |
| `m6-yard` | `--dev-mission6-yard` | Mission 6 straight into the 'Who is Ucilev?' yard fight |
| `m6-ending` | `--dev-mission6-ending` | Mission 6 ending cutscene |
| `m6-heli` | `--dev-mission6-heli` | Mission 6 ending from the helicopter finale |
| `m7` | `--dev-mission7` | Mission 7 Fallow Ground from the top (arrival film) |
| `m7-arrival` | `--dev-mission7-arrival` | Mission 7 drop-off film, then the chores |
| `m7-chores` | `--dev-mission7-chores` | Mission 7 top-down farm chores |
| `m7-runner` | `--dev-mission7-runner` | Mission 7 Alex-on-the-bike film |
| `m7-prep` | `--dev-mission7-prep` | Mission 7 top-down prep (pick 2 of 3) |
| `m7-raid` | `--dev-mission7-raid` | Mission 7 3D raid, no preps (--m7-preps=tractor,shed,loft --m7-cp=1/2) |
| `m7-raid-prepped` | `--dev-mission7-raid-prepped` | Mission 7 3D raid with all three preps |
| `m7-raid-w2` | `--dev-mission7-raid-w2` | Mission 7 3D raid from checkpoint 1 (orchard cleared, trucks next) |
| `m7-raid-w3` | `--dev-mission7-raid-w3` | Mission 7 3D raid from checkpoint 2 (trucks cleared, barn fire next) |
| `m7-finale` | `--dev-mission7-finale` | Mission 7 burning-farm night film |
| `m7-choice` | `--dev-mission7-choice` | Mission 7 radio choice (sets the Mission 8 route) |
| `m7-outro` | `--dev-mission7-outro` | Mission 7 end, straight to mission complete (route defaults to duty) |
| `m8` | `--dev-mission8` | Mission 8 The Call, Revenge route from the top (meet beat) |
| `m8-trap` | `--dev-mission8-trap` | Mission 8 3D trap fight on Route 12 (--m8-cp=1/2/3) |
| `m8-gantry` | `--dev-mission8-gantry` | Mission 8 3D gantry climb to Vasile |
| `m8-friends` | `--dev-mission8-friends` | Mission 8 catwalk beat with Vasile |
| `m8-kill` | `--dev-mission8-kill` | Mission 8 standoff on the catwalk, one shot |
| `m8-chase` | `--dev-mission8-chase` | Mission 8 tractor chase (--m8-cp=1/2/3/4) |
| `m8-heli` | `--dev-mission8-heli` | Mission 8 tractor chase helicopter mini-boss |
| `m8-ending` | `--dev-mission8-ending` | Mission 8 chase ending at the crossing (last jeep down) |
| `m8-epilogue` | `--dev-mission8-epilogue` | Mission 8 epilogue films (State TV, Commander, funeral) |
| `m8-credits` | `--dev-mission8-credits` | Mission 8 end credits |
| `m8-duty` | `--dev-mission8-duty` | Mission 8 Head of State (Duty route) from approach |
| `m8-mansion` | `--dev-mission8-mansion` | Mission 8 3D Mansion fight with Bodi & Alex (--m8-cp=0..4) |
| `m8-hall` | `--dev-mission8-hall` | Mission 8 Mansion cp 1: Grand Hall & Andrei M. security room |
| `m8-study` | `--dev-mission8-study` | Mission 8 Mansion cp 3: kick Retardovici's study door |
| `m8-helipad` | `--dev-mission8-helipad` | Mission 8 Mansion cp 4: helipad terrace holdout |
| `m8-liftoff` | `--dev-mission8-liftoff` | Mission 8 study & helicopter liftoff 3D film |
| `m8-flight` | `--dev-mission8-flight` | Mission 8 Last Flight door-gunner chase (--m8-cp=0..4) |
| `m8-flight-road` | `--dev-mission8-flight-road` | Mission 8 Last Flight cp 1: Curfew Road chase |
| `m8-flight-tail` | `--dev-mission8-flight-tail` | Mission 8 Last Flight cp 3: Route 12 tail-rotor takedown |
| `m8-flight-ucilev` | `--dev-mission8-flight-ucilev` | Mission 8 Last Flight cp 4: Ucilev gunship duel |
| `m8-crash` | `--dev-mission8-crash` | Mission 8 Duty crash past the ridge 3D film |
| `m8-ridge` | `--dev-mission8-ridge` | Mission 8 Duty sniper ridge finale (Ucilev & Retardovici) |
| `m8-duty-epilogue` | `--dev-mission8-duty-epilogue` | Mission 8 Duty epilogue films (Capital Square inauguration) |
| `trailer-m1` | `--dev-m1-game` | Trailer Act I warehouse take (bot: breach/molotov) |
| `trailer-m2-killbox` | `--dev-mission2-game` | Trailer Act II killbox take (bot: OS-12 hold + flank) |
| `trailer-m2-evidence` | `--dev-mission2-evidence` | Trailer Act II evidence take (bot: control building) |
| `trailer-m3-breakout` | `--dev-mission3-game` | Trailer Act III breakout take (bot: shiv/sidearm) |
| `trailer-m3-comms` | `--dev-mission3-comms` | Trailer Act III relay take (bot: power->auth->tune, Volkov cover) |
| `slot-select` | `--dev-slot-select` | Save-slot screen directly (add --continue for CONTINUE variant) |
| `audio-parade` | `--dev-audio-parade` | Comms wing with verbose sound logging (volume tuning) |
| `mp-host` | `--dev-mp-host` | Multiplayer arena panel, hosting on --mp-port (default 27017) |
| `mp-join` | `--dev-mp-join` | Multiplayer arena panel, joining --mp-join ADDR (host:port) |
<!-- /AUTO:devjumps -->


## 20. Every source file (`src/`, generated from module docstrings)

Format: `file` lines - first docstring sentence (or public names). Content data under `src/game/content/` is in §14 and §8. Maintained by `python tools/sync_arch_map.py` (line counts, new/removed files; hand-edited descriptions are kept). Monolith slices: §20.1; slice bundles: `python tools/ai_bundle.py path:start-end`.

**`src/`**

- `app.py` 4795 - Public: `handle_settings_event`, `trigger_transition`, `CutscenePlayer`, `start_cutscene`, `apply_display_mode`, `draw_slot_select_screen`, `start_briefing`, `finish_briefing`

**`src/art/`**

- `__init__.py` 1 - Hand-authored pixel-art sprites (pygame-only, no game imports).

**`src/art/m5/`**

- `__init__.py` 24 - Shim (A-008): aliases every `art.m5.<name>` in `sys.modules` to `game.art.m5.<name>`.
- `_kit.py` + 20 sprite modules: **stale tracked copies, never executed** (the shim aliases win). Edit `src/game/art/m5/`.

**`src/audio/`**

- `__init__.py` 1 - audio package.
- `audio.py` 3454 - Public: `AudioManager`
- `mixlock.py` 63 - Pause/resume for the mixer without the alt-tab deadlock.
- `voice.py` 894 - Voice-over playback for Call of Acaristan.
- `voice_manifest.py` 614 - Generated from voice_lines.xlsx - (VO ID, speaker, line) for every voiced line.

**`src/core/`**

- `__init__.py` 1 - core package.
- `ambience.py` 183 - zone-driven world ambience layers.
- `appearance.py` 583 - Character appearance: the cosmetic catalog, the appearance value object, and the single validator that both the save...
- `artpack.py` 31 - core.artpack - deprecated path (RPE6 Phase 2, A-006).
- `camera.py` 341 - Shared camera and bullet helpers.
- `config.py` 905 - Public: `resource_path`, `windowed_size`, `make_grain`, `draw_sky_gradient`, `draw_building`, `draw_cityscape`, `draw_rain`, `rain_drawables`
- `console.py` 343 - Public: `Console`
- `cutscene_registry.py` 60 - Cutscene scene renderers registered by scene id (RPE6 D1, boundary rule 4).
- `dev_jumps.py` 189 - registry of dev jump targets.
- `fixedstep.py` 432 - Fixed-timestep accumulator, for making the simulation host-independent.
- `font_coverage.py` 60 - Font glyph coverage - the fontTools half of §6.13 (dev/audit only).
- `frame_pacer.py` 87 - Frame pacing for the 60 Hz fixed-step loop: `Pacer.wait()` once per frame in `app._legacy_frame`; whole steps per frame, 60/30 fps lock (bug-333).
- `fsm.py` 171 - Finite State Machine infrastructure for Acaristan.
- `game_core.py` 590 - Proxy facade that delegates to split modules.
- `hands.py` 299 - Canonical hand renderers - the reference-anatomy model (dorsal view).
- `interactions.py` 692 - Player interactions with the world: doors, safe, NPCs, alarms.
- `json_store.py` 41 - Shared atomic JSON persistence helpers for save_data.json / settings.json.
- `level_editor.py` 224 - Public: `LevelEditor`
- `lighting.py` 20 - core.lighting - deprecated path (RPE6 Phase 2, A-006).
- `mapbuilder.py` 143 - Shared tilemap authoring helper (pure python, no pygame).
- `mission_meta.py` 106 - Per-mission display metadata (operation name + failure-screen copy).
- `outfits.py` 161 - Biribel's Mission 5 kit, as data (one source of truth).
- `profile_store.py` 234 - The global profile: Acaribucks wallet, owned cosmetics, equipped loadout.
- `props.py` 378 - shared set-dressing prop painters.
- `render_util.py` 17 - core.render_util - deprecated path (RPE6 Phase 2, A-006).
- `save_system.py` 304 - 3-slot JSON save system for campaign progress.
- `scene_mirror.py` 70 - RPE6 ADAPTER A-005: mirror the legacy GameStateManager onto an engine SceneStack.
- `score.py` 150 - the OST under quiet gameplay (mission-keyed CALM/TENSE).
- `settings_store.py` 179 - Settings store - persistent JSON-backed user preferences.
- `state.py` 490 - Central game state singleton.
- `staticlayer.py` 109 - chunked bake of the static world (phase 0).
- `surfaces.py` 59 - floor-material zones for footstep timbre selection.
- `user_settings.py` 112 - Live user settings - shared across all gameplay modules.

**`src/cutscenes/`**

- `__init__.py` 46 - Package cutscenes - re-export facade.
- `cast.py` 112 - cutscene cast sprites.
- `cast3d.py` 156 - 3D (engine3d.Humanoid) looks derived from the 2D cast sheet.
- `chair.py` 1303 - Split part. (no docstring)
- `death3d.py` 747 - Gameplay death falls for 3D guards (Mission 7 raid, Mission 6 yard).
- `engine.py` 706 - Split part. Public: `draw_cutscene_scene`, `draw_typewriter_title`, `reset_dialogue_slide`, `draw_dialogue_box`, `draw_cinematic_subtitle`, `draw_film_caption`, `draw_volkov_dossier_overlay`
- `figure_kit.py` 11 - cutscenes.figure_kit - deprecated path (RPE6 Phase 2, A-006): the kit is ``engine.anim``.
- `fire3d.py` 898 - Shared procedural turbulent fire/smoke/ember system for 3D and 2.5D (24-frame cyclic flame atlas, pitch-aware `draw_depth`, `phys_occ`, `_gl_surf` ember beds).
- `intro3d.py` 1403 - engine3d takes for the opening narration (``core.cutscene1``).
- `k9.py` 406 - K-9 armory pickup: one continuous, deterministic, software-safe take.
- `m2route12_3d.py` 740 - route12_3d.py - engine3d takes for Mission 2's narrative cutscenes. (auto)
- `m3broadcast.py` 834 - Mission 3 - Kill Order -> Broadcast transition cinematic (Slice 5 -> 6).
- `m3broadcast3d.py` 456 - Seekable 3D bridge from the loading dock to the state television studio.
- `m3cell.py` 926 - Split part. (no docstring)
- `m3cell_balaceanu_patch.py` 7 - (no docstring)
- `m3ending.py` 382 - Mission 3 finale cutscene (the Vostral read live on air).
- `m3ending3d.py` 408 - m3ending3d.py - 3D engine3d takes for Mission 3's broadcast finale and 22:00 fail cut. (auto)
- `m3intro3d.py` 452 - m3intro3d.py - 3D engine3d takes for Mission 3's cold-open interrogation intro. (auto)
- `m3ko.py` 674 - Mission 3 - Kill Order transition cinematic (Slice 5 cutscene rehaul, v2).
- `m3ko3d.py` 425 - Kill Order intro: directed 3D breach, stairs, cover and empty-dock preview.
- `m3ops.py` 1224 - Split part. (no docstring)
- `m3staging.py` 386 - M3 service-exit bridge: one 3D set, four directed camera setups.
- `m4aftermath.py` 750 - Mission 4 finale + intro cutscene art (The Aftermath).
- `m4aftermath3d.py` 554 - m4aftermath3d.py - 3D engine3d takes for Mission 4's intro and ending cutscenes. (auto)
- `m5decal.py` 108 - Sprite -> wall decal mesh for the M5 3D cutscenes.
- `m5ending3d.py` 708 - Authored M5 ending set and distance-driven actor blocking.
- `m5fx3d.py` 637 - FX kit for the Mission 5 3D cutscenes (m5martial3d / m5mid3d; `_gl_spec`/`_gl_lines` + `night_sky(gpu=)`; clears stale sky via `set_sky(None)`).
- `m5harbour_art.py` 1038 - Authored blocky harbour art for M5; canonical people and motion stay intact.
- `m5martial.py` 693 - Mission 5 intro + ending cutscene art (Martial Law).
- `m5martial3d.py` 1232 - W7: true-3D (engine3d) takes of every Mission 5 cutscene.
- `m5mid3d.py` 2198 - Mission 5 mid-mission cutscenes (round 2).
- `m5shadow3d.py` 1209 - The rebuilt M5 finale: one fresh 3D set, actor clock and camera language.
- `m5studio.py` 149 - the state-TV studio shared by the M5 bulletin's 3D take (m5martial3d._bulletin) and its 2D fallback (m5martial._draw_...
- `m6films.py` 3218 - engine3d takes and 2D fallbacks for every Mission 6 film.
- `m6fx3d.py` 625 - the Mission 6 FX kit: late-PS2 night light, smoke and haze (+ `_gl_spec`, `cine_curve()`).
- `m6world3d.py` 2721 - engine3d sets and actor kit for the Mission 6 films (HDR on GL, `night(gpu=)`).
- `m7films.py` 252 - Mission 7 films: the dawn drop-off (beat 1), the raid lead-in (beat 5) and the burning farm (beat 6).
- `m7goat.py` 1020 - Mission 7 bridge: the wire was never mended, and Bodi's goat gets out.
- `m7goat3d.py` 325 - m7goat3d.py - 3D engine3d takes for Mission 7's goat-escape bridge. (auto)
- `m7palette3d.py` 91 - The 2D top-down M7 farm palette, for the 3D farm (raid and films).
- `m7pig3d.py` 281 - Bodi's low-poly pig and distance-driven, cached walk poses.
- `m7runner.py` 1355 - Mission 7 beat 3: Alex arrives with the mansion plan and a sketch of the farm.
- `m7world3d.py` 3281 - Mission 7 farm: shared 3D builder for the drop-off, finale and raid (delegates fire to `fire3d`; `raid_curve()`, GPU `finish`).
- `m8duty_crowd.py` 550 - m8duty_crowd.py - 42 unique Acaristan citizens for the M8 Duty epilogue. (auto)
- `m8duty_sets.py` 823 - Mission 8 Duty 3D sets: Capital Square Courthouse and Forest Crash Clearings. (auto)
- `m8dutyfilms.py` 1369 - Mission 8 Duty 3D films: Approach (aerial over the estate, the gate) and Liftoff (Biribel out on the terrace under Retardovici'...
- `m8films.py` 1112 - Mission 8 Revenge films: the meet at Route 12, Old Friends on the catwalk, and the epilogue.
- `oil_rig_3d.py` 139 - True-3D Oil Rig Bombing cutscene (engine3d; rig fires via `fire3d.emit_fire`).
- `post3d.py` 219 - Cinematic post stack for cutscene shots (RPE6 Phase 11 step 5).
- `ps2mat.py` 100 - PS2 pixel textures for sets authored in flat colour.
- `revive3d.py` 512 - Shared 3D ally-revive choreography (M7 raid, M8 trap, M8 mansion): four-stage hand-clasp pull-up, living downed pose, world-space IK clasp, ground rifles, revive framing camera.
- `route12.py` 1874 - Split part. Public: `draw_factory`, `draw_oil_rig`, `draw_propaganda_poster`, `draw_mag_graffiti`, `draw_van_exterior`, `draw_van_interior`, `draw_van_handoff`, `draw_route12_black`
- `van3d.py` 890 - engine3d take of the KRAP van establishing shot (scene ``van_exterior``).
- `weather3d.py` 152 - Data-driven weather & atmosphere for 3D sets (RPE6 Phase 11 step 6).

**`src/engine/`**

- `__init__.py` 9 - Retardovici Pulse Engine 6 Gold (RPE6): the Call of Acaristan engine.

**`src/engine/ai/`**

- `__init__.py` 27 - engine.ai - enemy brains: behaviour trees, senses, squads and cover.
- `bt.py` 275 - engine.ai.bt - a small behaviour tree runtime.
- `cover.py` 143 - engine.ai.cover - cover spots around solid boxes, and picking one.
- `senses.py` 131 - engine.ai.senses - what an agent knows about its target.
- `squad.py` 91 - engine.ai.squad - what a group of agents shares.

**`src/engine/anim/`**

- `__init__.py` 36 - engine.anim - animation (RPE6).
- `figure_kit.py` 1754 - shared cast renderer in the "Balaceanu Arrest" house style.
- `pose_cache.py` 50 - Pose cache: render-once surfaces for parameterised procedural bodies.
- `rig3d.py` 523 - Layered 3D pose controller, velocity-coupled gait, and stair/foot-IK solver. (auto)
- `springs.py` 194 - Analytical spring-damper primitives for 3D procedural animation & camera feel. (auto)

**`src/engine/assets/`**

- `__init__.py` 39 - engine.assets - asset access (RPE6).
- `_artpack.py` 288 - loaded-sprite registry with procedural fallback.
- `_sprites.py` 44 - tiny cached PNG loader with graceful fallback.
- `bake.py` 414 - Deterministic bake + content hashing + lint for rendered assets (§6.5).
- `layerbake.py` 286 - Bake camera-space procedural painters into world layers (Phase 3 conversion kit).
- `loaders.py` 54 - Raw file loaders: the only place in the codebase that may call ``pygame.image.load`` / ``pygame.mixer.Sound`` on game...
- `manifest.py` 125 - Content-pack manifests (§6.5): ``ae.manifest/1``.
- `registry.py` 356 - AssetRegistry (§6.5): stable ids, the fallback chain, caching, ref-counts, reload.
- `watch.py` 70 - Hot reload for development (§6.5): poll the files behind loaded assets and call ``AssetRegistry.reload`` when one cha...

**`src/engine/collision/`**

- `__init__.py` 20 - engine.collision - solid-world queries for gameplay (RPE6 §6.9).
- `boxes.py` 151 - engine.collision.boxes - ray, segment and body queries against AABBs.
- `mesh.py` 621 - engine.collision.mesh - exact hitboxes from a mesh's own triangles (local 3D AABB ray/body early-out, LRU-free grid).
- `nav.py` 649 - engine.collision.nav - A* on a walkability grid (RPE6 §6.9 ``GridGraph``).
- `physics.py` 852 - Shared capsule sliding, rigid impact debris, and articulated Verlet ragdolls. (auto)

**`src/engine/core/`**

- `__init__.py` 23 - engine.core: kernel services (clock, rng, events, log, config, services, errors, app).
- `app.py` 142 - App: explicit boot / run / shutdown (§6.1).
- `clock.py` 117 - Fixed-step simulation clock (master prompt §6.1, ADR-004).
- `config.py` 67 - Layered settings: defaults < JSON file < environment < CLI overrides (§6.1).
- `errors.py` 53 - Engine exceptions with context, and the crash-report writer (§6.1, §6.23).
- `events.py` 73 - Typed event bus (§6.3).
- `log.py` 62 - Structured logging with channels, a ring buffer and warn-once (§6.23).
- `mathx.py` 41 - Small math helpers (lerp/ease/angles/clamp).
- `profiling.py` 31 - Scoped timers (§6.22).
- `rng.py` 63 - Named, seeded random streams (R6, §6.1).
- `services.py` 39 - Explicit service registry (§6.1): no magic globals, clear errors.
- `timebase.py` 67 - Game-time accessors for legacy code (RPE6 ADAPTER A-004, BUGS B-001).

**`src/engine/dialogue/`**

- `__init__.py` 28 - engine.dialogue - data-driven dialogue (RPE6 §6.14, Phase 7).
- `model.py` 139 - dialogue.model - the .dlg.json model and static validation (RPE6 §6.14).
- `runner.py` 153 - dialogue.runner - DialogueRunner: walk a .dlg.json graph, emit lines (RPE6 §6.14).

**`src/engine/input/`**

- `__init__.py` 12 - engine.input - action maps over raw device state (RPE6 §6.10, Phase 9).
- `model.py` 110 - input.model - action maps and pressed-state remapping (RPE6 §6.10, Phase 9).

**`src/engine/level/`**

- `__init__.py` 24 - engine.level - data-driven levels (RPE6 §6.16, Phase 7).
- `model.py` 146 - level.model - the .level.json model, validation and (de)serialisation (RPE6 §6.16).
- `tiled.py` 89 - level.tiled - Tiled JSON (.tmj) importer (RPE6 §6.16).

**`src/engine/lighting/`**

- `__init__.py` 8 - engine.lighting - 2D light map (RPE6).
- `buffer.py` 339 - lighting.buffer - half-res light buffer: grade, motivated pools, dust (engine side).
- `lightmap.py` 114 - lighting.lightmap - multiplicative 2D light map (RPE6 Phase 6, §6.6 lighting integration).

**`src/engine/render2d/`**

- `__init__.py` 29 - engine.render2d - one way to put pixels on screen during gameplay (RPE6 §6.6).
- `camera.py` 159 - render2d.camera - Camera2D: follow, dead-zone, look-ahead, bounds, trauma shake, zoom (RPE6 §6.6).
- `drawables.py` 465 - render2d.drawables - the things a RenderQueue draws (RPE6 §6.6, Phase 6).
- `pen.py` 109 - render2d.pen - a drawing sink for procedural painters (RPE6 Phase 6, B-033).
- `postfx.py` 154 - render2d.postfx - full-screen post effects as cached surfaces + parameters (RPE6 §6.6).
- `queue.py` 185 - render2d.queue - the sorted render queue and its layer table (RPE6 §6.6, Phase 6).
- `static.py` 141 - render2d.static - StaticLayers: chunked bakes of floor/decor painters (RPE6 §6.6).
- `util.py` 135 - render2d.util - shared gameplay-render helpers (engine side).

**`src/engine/render3d/`**

- `__init__.py` 35 - engine.render3d - declarative 3D sets (RPE6 §6.7, Phase 8).
- `blast_sprites.py` 280 - Procedural cached fireball, blast flash, and ground-flash 3D sprites. (auto)
- `presets.py` 153 - render3d.presets - named 3D lighting moods (RPE6 §6.7 step 1, Phase 11).
- `scene3d.py` 317 - render3d.scene3d - declarative 3D sets (RPE6 §6.7, Phase 8).
- `vehicle_destruction.py` 1383 - Shared 3D vehicle destruction physics, authored profiles, and rendering. (auto)

**`src/engine/save/`**

- `__init__.py` 13 - engine.save - snapshots and determinism hashing (RPE6 §6.17, Phase 9).
- `snapshot.py` 76 - save.snapshot - the ae.save/1 snapshot model (RPE6 §6.17, Phase 9).
- `statehash.py` 43 - save.statehash - stable world hashing for determinism checks (RPE6 §6.17).

**`src/engine/scene/`**

- `__init__.py` 9 - engine.scene - explicit scene stack (RPE6 §6.2).
- `cutscene.py` 126 - CutsceneScene: a linear sequence of timed shots (§6.2, Phase 2 form).
- `inspect.py` 55 - InspectScene: a first-person look at an object that freezes gameplay (§6.2).
- `scene.py` 74 - Scene: one screen of the game with an explicit lifecycle (§6.2).
- `stack.py` 257 - SceneStack: the explicit replacement for stage flags and mode switches (§6.2).

**`src/engine/settings/`**

- `__init__.py` 13 - engine.settings - typed, layered user settings (RPE6 §6.18, Phase 9).
- `model.py` 175 - settings.model - typed, layered settings (RPE6 §6.18, Phase 9).

**`src/engine/text/`**

- `__init__.py` 29 - engine.text - string tables, the font registry and text layout (§6.12/§6.13).
- `fonts.py` 90 - Font registry and the glyph verdict (§6.13).
- `layout.py` 116 - Text layout: measure, wrap, fit, ellipsis (§6.12).
- `strings.py` 89 - String tables (§6.13): keys -> English, ``T()`` with fallbacks.

**`src/engine/timeline/`**

- `__init__.py` 25 - engine.timeline - data-driven cutscene timelines (RPE6 §6.15, Phase 8).
- `expr.py` 109 - timeline.expr - the tiny safe expression evaluator (RPE6 §6.7/§6.15).
- `model.py` 165 - timeline.model - the .timeline.json model and static validation (RPE6 §6.15).
- `player.py` 166 - timeline.player - deterministic sampling of a Timeline at any t (RPE6 §6.15).

**`src/engine/ui/`**

- `__init__.py` 25 - engine.ui - the widget kernel and the standard widgets (§6.12, Phase 4).
- `theme.py` 115 - Theme: the fonts, colours and viewport metrics widgets draw with (§6.12).

**`src/engine/ui/std/`**

- `__init__.py` 13 - Standard widgets, extracted from what the missions already draw (§6.12).
- `bottle_hud.py` 44 - BottleHud - the molotov counter strip (M1 + M2; the bodies were identical).
- `crosshair.py` 67 - Crosshair - the aim reticle shapes (four-arm reticle; combat ring + arms).
- `dialogue_box.py` 166 - DialogueBox: the shared cutscene dialogue box (A6.11, Phase 4).
- `health_bar.py` 57 - HealthBar - the HP strip (panel + "HP" label + ratio bar).
- `hostiles.py` 30 - Hostiles - the HOSTILES counter box.
- `minimap.py` 429 - MiniMap - the corner minimap panel.
- `objective_banner.py` 110 - ObjectiveBanner - the OBJECTIVE panel.
- `prompt.py` 71 - prompt - the world-anchored interaction tag ("[E] ...") drawn over a spot.
- `weapon_panel.py` 125 - WeaponPanel (MagIcons) - the 84px magazine-icon weapon panel.

**`src/engine/world/`**

- `__init__.py` 21 - engine.world - entities, components, systems ("ECS-lite", RPE6 §6.4).
- `_component.py` 125 - engine.world._component - ``@component`` dataclasses and the schema registry (RPE6 §6.4, A.1).
- `entity.py` 227 - engine.world.entity - ``EntityId`` and ``World`` storage (RPE6 §6.4).
- `prefab.py` 134 - engine.world.prefab - data-defined entity templates with inheritance (RPE6 §6.4, B.4).
- `std.py` 164 - engine.world.std - standard components (RPE6 §6.4).
- `system.py` 145 - engine.world.system - ``System`` base, phases and the ``Scheduler`` (RPE6 §6.4, A.1).

**`src/engine3d/`**

- `__init__.py` 15 - engine3d - tiny flat-shaded low-poly software renderer for pygame.
- `core.py` 1042 - Core of the low-poly renderer: math, meshes, camera, painter renderer (backend-parity `set_sky` stub).
- `gl.py` 2195 - engine3d.gl - GPU backend (ModernGL): RGBA16F MRT FBO + `gl_sprites`/`gl_post` integration; `flush_to`/`present_to` single-readback path (`add_blob_shadow` queues GPU `_gl_spec`).
- `gl_post.py` 1120 - GPU HDR bloom, 2.5D lightmap, LUT grade, dither and crisp upscale (Phase 1).
- `gl_sprites.py` 1068 - GPU sky pass and sprite/line batching for GLRenderer (Phase 1).
- `hold.py` 346 - Weapon holds and arm-vs-body safety for the box rig (engine3d.rig.Humanoid).
- `ik.py` 294 - Analytic two-bone IK for the box rig (engine3d.rig.Humanoid).
- `particles.py` 326 - Shared vectorized particle & ground-decal pools with GPU instancing support. (auto)
- `rig.py` 1394 - Low-poly humanoid rig: boxes on a joint hierarchy, posed by angle dicts.
- `textures.py` 164 - engine3d.textures - pixel textures on world faces.

**`src/entities/`**

- `__init__.py` 1 - entities package.
- `adornments.py` 249 - Head gear, as a registry keyed by catalog id.
- `art_cache.py` 424 - Centralized procedural surface cache for Call of Acaristan.
- `corpse.py` 560 - Enemy death corpses - bodies that fall instead of vanishing.
- `death_anim.py` 502 - Death animation - Option B (Standard).
- `enemy_ai.py` 1082 - Public: `Enemy`, `enemy_hear_shot`
- `fallen.py` 356 - A fallen body for a player, drawn in the same visual language as enemies.
- `player.py` 738 - Player character: movement, drawing, weapon rig.
- `sprite_lib.py` 11 - entities.sprite_lib - deprecated path (RPE6 Phase 2, A-006): see ``engine.assets.sprites``.
- `weapon_rig.py` 456 - The three weapon rigs, as drawable-on-call functions.
- `weapons.py` 851 - Player weapons: pistol, melee, molotov cocktails, fire zones (cached FireZone surfaces).

**`src/fx/`**

- `__init__.py` 1 - fx package.
- `effects.py` 156 - Visual effects: particles, casings, breach markers, blood decals.

**`src/game/`**

- `__init__.py` 3 - Game-owned content (RPE6 Phase 3): art packs under ``game.art`` and pack manifests under ``game/content/<pack>/``.
- `devtools.py` 352 - RPE6 Phase 10 (§6.19): in-game debug tools.
- `dialogues.py` 84 - game.dialogues - mission conversation access (RPE6 Phase 7).
- `input_adapter.py` 144 - RPE6 Phase 9: game-side input adapter (rebinding + gamepad).
- `levels.py` 48 - game.levels - level-data access for the missions (RPE6 §6.16, Phase 7).
- `rain3d.py` 387 - World-space 2.5D rain for top-down 3D views (Walk, M1, M4, M5). (auto)
- `render3d_bridge.py` 679 - game.render3d_bridge - apply ae.set3d/1 data to a live 3D renderer (RPE6 Phase 8).
- `save_adapter.py` 392 - RPE6 Phase 9: game-side adapter between live state and ``engine.save``.
- `scenery3d.py` 92 - Cached office and medical scenery, baked offline from the source GLBs.
- `timelines.py` 74 - game.timelines - cutscene shot-list access (RPE6 Phase 8).
- `topdown3d.py` 650 - Shared 2.5D host for the top-down game: camera, sim<->world mapping, aim (GPU blob/ring/blood `_gl_spec`/`_gl_surf`).
- `vehicle_fx.py` 38 - Game-side FX adapter for ``engine.render3d.VehicleDestructionManager``. (auto)

**`src/game/art/`**

- `__init__.py` 3 - Hand-authored pixel-art packs (pygame-only).
- `_layers.py` 54 - Shared helpers for baked world layers (``game.art.<pack>.<name>`` adapter modules).
- `_pack.py` 109 - Per-pack registry wrappers for game code (``game.art.<pack>``).

**`src/game/art/m1/`**

- `__init__.py` 23 - Mission 1 asset pack: baked world layers (and props) of the mission dressing.
- `exfil_truck.py` 20 - Mission 1 parked KRAP exfil flatbed (shadow, bed, crates, cab, headlights, wheels, KRAP label), baked from ``missions...
- `molotov_icon.py` 20 - HUD Molotov icon (0 active = lit bottle, 1 spent = grey bottle), baked from ``missions.m1.draw._paint_molotov_icon``...
- `pickup_icon.py` 20 - Mission 1 ground-pickup icons (0 magazine, 1 keycard, 2 bandage, 3 bottle), baked from ``missions.m1.draw._paint_m1_p...
- `world_static.py` 29 - Mission 1 static world (office floor grid, container / warehouse walls, desk bodies, bay label, dressing) baked from...

**`src/game/art/m2/`**

- `__init__.py` 23 - Mission 2 asset pack: baked world layers (and props) of the mission dressing.
- `nest_bits.py` 22 - Pieces of the abandoned Route 12 sniper nest (0 scuff ellipse 48x24, 1 brass casing 8x6, 2 left-behind rifle 40x12),...
- `prop_icon.py` 25 - Mission 2 clue / evidence prop icons at world scale (PROP_WORLD_SCALE), baked from ``missions.m2.draw._paint_prop_ico...
- `world_static.py` 33 - Mission 2 static world (road / terrain tiles, static dressing, structure walls, control facade, gantry, shelter, gard...

**`src/game/art/m3/`**

- `__init__.py` 23 - Mission 3 asset pack: baked world layers of the prison dressing (and later props).
- `archives_static.py` 39 - Archives Wing static world baked from ``missions.m3.draw._bake_m3_archives`` (live fallback).
- `broadcast_static.py` 26 - Broadcast Wing static world baked from ``missions.m3.draw._bake_m3_broadcast`` (live fallback).
- `camera_body.py` 19 - Mission 3 security-camera mount + smoked dome (0 idle, 1 alerted = opaque dome), baked from ``missions.m3.systems._pa...
- `cell_details.py` 25 - Biribel's cell dressing (cot, chair, sink, drain, stains, tally marks, conduit) as a baked world layer.
- `cell_door_blown.py` 21 - Mission 3 interrogation-cell door after the C4 breach has settled: jambs, the two door tiles, blast hole, scorch, cra...
- `cellblock_static.py` 45 - Cell-block map static world (floors, exterior ground, background dressing, corridor / guard room / armory / service-w...
- `comms_static.py` 26 - Comms Wing static world baked from ``missions.m3.draw._bake_m3_comms`` (live fallback).
- `door_tile.py` 25 - Reinforced prison door tile of Mission 3 (frame + leaf / open inner + padlock / LED) in its two rest states, baked fr...
- `kitchen.py` 30 - Prison kitchen / utility room of the cell block (floor tiles, backsplash, shelves, fixtures, grime) as a baked world...
- `ko_static.py` 42 - Kill Order ground-floor static world (floors, exterior ground, set dressing: stairwell, dock crane, crates, mezzanine...
- `pickup_icon.py` 20 - Mission 3 ground-pickup markers (0 looted sidearm, 1 bandage), baked from ``missions.m3.draw._paint_m3_pickup_icon``...
- `wall_monitor.py` 24 - Interrogation-cell wall monitor (Mission 3), baked from ``missions.m3.draw._paint_wall_monitor_part`` (live fallback).
- `weapon_icon.py` 20 - Mission 3 HUD weapon icons (shiv, chair leg, K-9 SMG, looted sidearm, generic), baked from ``missions.m3.systems._pai...

**`src/game/art/m4/`**

- `__init__.py` 23 - Mission 4 asset pack: baked world layers (and props) of the mission dressing.
- `mag_icon.py` 25 - Mission 4 HUD magazine icons, baked from ``missions.m4.draw._paint_m4_mag_icon`` (live fallback).
- `world_static.py` 42 - Mission 4 static world (floor + walls, buildings, roofs, window grids, storefronts, ground dressing) baked from ``mis...

**`src/game/art/m5/`**

- `__init__.py` 79 - Mission 5 sprite pack (owner module; ``art.m5`` is the compatibility shim).
- `_kit.py` 128 - Shared pixel-art kit for the Mission 5 sprites.
- `armband.py` 21 - The black Guard armband pinned to the depot notice board (25 x 8 px, 0.5 x 0.16 m): black cloth with a red stripe, fo...
- `bale.py` 52 - Strapped newspaper bundles seen from above (Print Works stacks/pallets).
- `calendar.py` 24 - Safehouse wall calendar (24 x 32 px, 0.6 x 0.8 m): red 1991 header, month grid, one day ringed in red, nail at the top.
- `district_map.py` 34 - Vasile's district map (52 x 36 px, 1.3 x 0.9 m): street grid, the river, the Lower Quarter ringed in red, "SECTOR 4"...
- `guard_banner.py` 44 - Presidential Guard banner (36 x 57 px, 1.2 x 1.9 m): brass rod, black cloth with folds lit from the left, gold eagle,...
- `guard_plate.py` 15 - Lit red Guard notice plate over the Print Works door (36 x 20 px, 0.9 x 0.5 m).
- `hq_locker.py` 29 - Guard HQ steel locker (26 x 44 px, top-down gameplay prop).
- `inspect_art.py` 30 - Static layers of the Mission 5 "[E] look" first-person shots (canvas CW x CH = 1.3x screen).
- `m5_guard.py` 62 - Presidential Guard trooper, top-down gameplay sprite (96 x 96, figure centred at (48, 48), facing +x).
- `mag.py` 30 - Maru's thrown magazines (gameplay).
- `mag_icon.py` 126 - HUD magazine-icon shells (weapon panel).
- `maru.py` 29 - Maru, top-down gameplay sprite (84 x 84, anchor (42, 48) = feet/centre): the figure_kit cast look - black hoodie, pis...
- `plate.py` 23 - HUD status plate (convoy / raid clock), 340 x 46: dark glass, steel rim with a lit top edge (upper-left key light), e...
- `portrait_frame.py` 31 - Official portrait of President Retardovici in a gilt frame (30 x 30 px, 1.0 x 1.0 m).
- `posters.py` 128 - Wall posters of the Lower Quarter (32 x 44 px, 0.64 x 0.88 m in the 3D sets).
- `presidential_crest.py` 64 - State crests (40 x 40 px).
- `press.py` 51 - Print Works offset press, top-down (154 x 64).
- `printworks_sign.py` 24 - "MAG PRINT WORKS" enamel sign over the Print Works (96 x 14 px, 8.4 x 1.3 m).
- `tram_wreck.py` 20 - Burnt-out tram on the quarter junction (static decor).
- `wall_posters.py` 64 - Top-down wall posters for the gameplay maps (the wall is seen as its front band).

**`src/game/content/`**

- `__init__.py` 1 - Pack manifests (``ae.manifest/1``) and palettes, one folder per pack.

**`src/game/render/`**

- `__init__.py` 72 - game.render - the game's ``engine.render2d`` instance: queue + static layers + post-FX + camera (RPE6 Phase 6).
- `adapters.py` 62 - Drawable adapters for shared legacy classes (RPE6 Phase 6, ADR-017).
- `host.py` 78 - game.render.host - the game's render2d instance and the hosted gameplay frame (RPE6 §6.6, Phase 6).

**`src/game/world/`**

- `__init__.py` 158 - game.world - the game's ``engine.world`` instance: World + Scheduler + legacy roster (RPE6 Phase 5).
- `legacy.py` 491 - game.world.legacy - strangler bridge between the pre-ECS objects and ``engine.world`` (RPE6 §6.4 step 1).

**`src/launcher/`**

- `__init__.py` 80 - Pre-game KRAPNET Launcher and in-place auto-updater package.
- `updater.py` 1316 - Update checker and in-place patcher for Call of Acaristan.
- `window.py` 1250 - KRAPNET Pre-Game Launcher window (Pygame) for Call of Acaristan.

**`src/missions/`**

- `__init__.py` 1 - missions package.
- `arena.py` 1742 - Multiplayer arena maps and the deathmatch rules.
- `walk3d.py` 605 - Walking sim in 2.5D: the harbour alley drawn in 3D over the 2D rules (HDR scoped off/restored).
- `walk_fp.py` 1164 - First-person reward cinematics for the walking sim.
- `walk_van3d.py` 152 - Walking sim: the KRAP extraction van as a real 3D model.
- `walking_attack3d.py` 890 - True 3D oil-rig strike cinematic, rendered by the game's engine3d (flames/smoke via `fire3d`).
- `walking_sim.py` 3554 - Walking sim section: slum exploration, NPCs, firefight overlook panorama.

**`src/missions/m0/`**

- `__init__.py` 482 - Mission 0 - Depot - thin host generated by tools/ae_new_mission.py (RPE6 P10).

**`src/missions/m1/`**

- `__init__.py` 42 - Package missions/m1 - re-export facade.
- `draw.py` 2455 - Split part. Public: `game_draw`, `submit_frame`
- `draw3d.py` 1917 - Mission 1 in 2.5D: the warehouse frame drawn in 3D over the 2D rules (shared `fire3d` flames/ember beds, `"fire"` grade lights, GL `flush_to`, HDR scoped).
- `escape3d.py` 320 - Mission 1 escape cut (timeline m1.escape) in 3D.
- `grade3d.py` 234 - Mission 1–5 / Walk / Arena night grade for 2.5D frames (LRU caches, `"fire"` light kind with warm spill + post-grade bloom).
- `hotwire.py` 144 - Split part. Public: `handle_hotwire_press`, `handle_hotwire_click`
- `m1_audio.py` 100 - Mission 1 music hook: two looped stems (infiltrate / combat), crossfaded over 1.5 s when the alarm flips STATE.firefi...
- `main.py` 363 - Split part. Public: `start_mission`
- `map.py` 175 - Mission 1 map - authored with core.MapBuilder, baked to list[str].
- `meta.py` 96 - Mission 1 cutscene data (RPE6 Phase 8 + WP2: the cut as ae.timeline/1).
- `roles.py` 233 - Mission 1 breach roles (WP7): rusher / cover / flanker per wave enemy, and CIOCAN's shoulder charge.
- `stealth.py` 431 - Mission 1 stealth (rework WP5, plan section d).
- `update.py` 1217 - Split part. Public: `debug_jump_to_exfil`, `standoff_commander`, `game_update`

**`src/missions/m2/`**

- `__init__.py` 54 - Package missions/m2 - re-export facade.
- `components.py` 19 - Mission 2 entity components (RPE6 Phase 5, D4).
- `draw.py` 8096 - Split part. Public: `draw_route12_seby_pickup`, `clamp_alpha`, `game_draw`, `get_mission2_overview`, `get_opening_cinematic`, `get_squadmate_death_cutscene`, `get_mission_phases`, `get_mission2_zones`
- `draw3d.py` 1548 - Mission 2 in 2.5D: Route 12 drawn in 3D over the 2D rules (HDR scoped off/restored).
- `meta.py` 702 - Split part. Public: `get_zone_for_world_pos`
- `sniper.py` 1984 - Split part. Public: `grant_seby_os12`
- `sniper3d.py` 1225 - Mission 2 - "Route 12 Kill-Box": the sniper ambush as a low-poly 3D film.
- `sniper3d_set.py` 274 - Route 12 toll plaza, built for the low-poly sniper cinematic.
- `starts.py` 608 - Split part. Public: `start_mission2`, `start_mission2_sniper`, `start_mission2_after_sniper`, `start_mission2_flank`, `start_mission2_truck`, `start_mission2_checkpoint`, `start_mission2_evidence_debug`
- `update.py` 1264 - Split part. Public: `handle_interact`, `blocks_player_actions`, `debug_jump_to_evidence`, `game_update`
- `world.py` 900 - Split part. (no docstring)

**`src/missions/m3/`**

- `__init__.py` 100 - Package missions/m3 - re-export facade.
- `components.py` 53 - Mission 3 entity components (RPE6 Phase 5, D4).
- `draw.py` 8367 - Split part. Public: `draw_archives_transition_cinematic`, `draw_vostral_pickup_cinematic`, `game_draw`, `solid_walls_view`
- `draw3d.py` 1443 - Mission 3 in 2.5D: the five playable maps drawn in 3D over the 2D rules (off-screen fire-zone cull, HDR scoped off/restored).
- `flow.py` 1954 - Split part. Public: `start_mission3`, `start_mission3_breakout_checkpoint`, `start_mission3_comms_checkpoint`, `start_mission3_archives_checkpoint`, `start_mission3_kill_order_checkpoint`, `start_mission3_broadcast_checkpoint`, `start_mission3_upload_checkpoint`
- `interrog.py` 638 - Split part. (no docstring)
- `maps.py` 836 - Split part. (no docstring)
- `meta.py` 566 - Split part. (no docstring)
- `sweep.py` 1125 - Slice 5b-5d: the Kill Order sweep director, overwatch pin, Volkov extraction window and dock holdout.
- `systems.py` 4209 - Split part. Public: `game_update`, `is_crafting_active`, `grant_k9_smg`, `start_black_ledger_debug`, `handle_interact`, `start_crafting`, `handle_crafting_event`, `handle_event`
- `wings3d.py` 746 - Mission 3 wings in 2.5D: the comms wing, the archives, the kill order floor and the broadcast studio, for ``draw3d``.
- `world.py` 2349 - Split part. (no docstring)

**`src/missions/m4/`**

- `__init__.py` 103 - Mission 4: The Aftermath - the world after the broadcast.
- `apc.py` 143 - Mission 4 wave 5: the APC ram.
- `components.py` 28 - Mission 4 entity components (RPE6 Phase 5, D4).
- `draw.py` 2922 - Split part. Public: `game_draw`
- `draw3d.py` 1704 - Mission 4 in 2.5D: human-proportioned curfew street (taller blocks, animated 3x4 Corner Alimentara with oscillating wall fan) and the radio station in 3D (HDR scoped off/restored).
- `escort.py` 150 - Mission 4 escort: Vasile, the KRAP comms cache and the supply pool.
- `flow.py` 849 - Split part. Public: `handle_dialogue_event`, `start_m4`, `start_mission4_station_checkpoint`, `start_mission4_tower_checkpoint`, `handle_interact`; owns the inside-only corner-shop visit/loot flags.
- `fortify.py` 219 - Mission 4 fortify: barricade sites, the build / upgrade / repair holds.
- `maps.py` 464 - Split part. Public: `zone_at`, `zone_label`; 3x4 corner-shop door/rect/counter constants and the 2-row station FOYER.
- `meta.py` 314 - Mission 4 - part module.
- `siege.py` 684 - Mission 4 siege: five waves on the station while the arrest airs.
- `systems.py` 454 - Split part. Public: `game_update`
- `world.py` 844 - Split part. Public: `friendly_npcs`, `barricade_blocks_shots`, `fail_mission`; `_shop_counter_pos`.

**`src/missions/m5/`**

- `__init__.py` 73 - Mission 5: Martial Law - the capital under emergency rule.
- `components.py` 29 - Mission 5 entity components (RPE6 Phase 5, D4).
- `decor.py` 380 - Mission 5 set dressing, lighting and inspectables (round 2).
- `decor_interior.py` 432 - Mission 5 interior set dressing (gauntlet pass).
- `decor_paint.py` 416 - Mission 5 static set dressing painters (round 2).
- `draw.py` 1400 - Mission 5 - part module.
- `draw3d.py` 1817 - Mission 5 in 2.5D: Guard HQ, the Lower Quarter, the print works and the tunnel in 3D (HDR scoped on/restored).
- `finale_audio.py` 272 - Mission 5 sound design and cutscene-owned playback.
- `finale_script.py` 43 - M5 rebuilt finale: immutable script/timing shared by renderer and player.
- `flow.py` 627 - Mission 5 - part module.
- `inspect_art.py` 370 - painters for the Mission 5 first-person inspect shots.
- `inspect_art_street.py` 253 - storeroom + Lower Quarter inspect shots (paint tins, shop TV through the shutter, the burned tram).
- `inspect_fpv.py` 232 - Mission 5 "[E] look": a short first-person look at the thing instead of a radio line.
- `maps.py` 270 - Mission 5 - part module.
- `meta.py` 265 - Mission 5 - part module.
- `quarter.py` 527 - Lower Quarter systems (round 2): turns 'run and gun' into a run with choices.
- `render.py` 119 - Mission 5 - part module.
- `systems.py` 368 - Mission 5 - part module.
- `tram_wreck.py` 531 - M5 Lower Quarter: the burning tram wreck (top-down).
- `water.py` 103 - M5 shallow floodwater: one connected, world-space surface, never tile stamps.
- `world.py` 762 - Mission 5 - part module.

**`src/missions/m6/`**

- `__init__.py` 57 - Mission 6: Whiteout - re-export facade (load order = parts order).
- `combat.py` 838 - Mission 6 - loud combat arenas for the three top-down stages.
- `decor.py` 2676 - Mission 6 - stage decor, ground art and night lighting.
- `draw.py` 698 - Mission 6 gameplay renderer.
- `draw3d.py` 1645 - Mission 6 in 2.5D: all four top-down stages (customs, no-man's-land, rail, boxcar folded into rail) with GPU extra-texture UVs (warm fire lightmap; HDR/dither/PS1 snap forced off and restored for key-colour decode).
- `flow.py` 395 - Mission 6 - stage ladder, checkpoints and the ending handoff.
- `hud3d.py` 262 - Mission 6 3D HUD: minimal tactical, shared by the train shootout and the yard fight.
- `hud_ui.py` 87 - Mission 6 tactical HUD styling & unified top-left combat cluster.
- `m6_audio.py` 678 - Mission 6 sound design: film stems, foley and the interactive-train bed.
- `maps.py` 298 - Authored map layer for Mission 6 - three distinct playable spaces.
- `meta.py` 314 - Mission 6 metadata, stage constants and authored cutscene timelines.
- `night_fx.py` 349 - Mission 6 night atmosphere: cached light sprites with the filmic curve baked in, pre-baked wet puddle patches, snow layers.
- `palette3d.py` 40 - The 2D top-down M6 palette, for the 3D yard and train.
- `perf.py` 386 - M6 3D scene performance governor (train scene + rail-yard fight).
- `stealth.py` 423 - Mission 6 - tower searchlights for no-man's-land and the rail yard.
- `systems.py` 316 - Mission 6 - per-frame gameplay pipeline.
- `train3d.py` 5422 - Mission 6 - the interactive 3D train scene (``docs/MISSION6_PLOT.md``; cached fade veil, corpse joints reused from `add_humanoid`, GPU reticle alpha via RGBA_MULT).
- `world.py` 432 - Mission 6 - world construction, Guard spawns and shared helpers (perimeter `"D"` tiles are solid).
- `yard3d.py` 2077 - Mission 6 - "Who is Ucilev?": the third-person fight after Volkov's death.
- `yard_brain.py` 613 - Mission 6 yard - the Guard brains (engine.ai on the "Who is Ucilev?" fight).
- `yard_dress.py` 304 - Mission 6 yard - the clutter that makes the walled yard look lived in.
- `yard_hud.py` 179 - Mission 6 yard - the 2D top-down game's HUD, brought into the 3D fight.

**`src/missions/m6/bloc3d/`**

- `__init__.py` 15 - bloc3d - the Bloc around the M6 yard and station, built from boxes.
- `blocks.py` 204 - Prefab Soviet panel blocks for the Bloc district.
- `colours.py` 39 - Phase-5 colours for the Bloc landmarks and signage.
- `font.py` 108 - A 5x7 pixel font for the Cyrillic signage on the Bloc.
- `signs.py` 172 - Cyrillic signage for the Bloc: rooftop letters, boards, stars, billboards, banners.
- `stacks.py` 134 - Industrial silhouettes on the skyline: chimneys, a radio mast, a water tower.
- `tower.py` 139 - Watchtowers and wire fences for the Bloc yards.

**`src/missions/m7/`**

- `__init__.py` 9 - Mission 7: Fallow Ground - re-export facade (load order = parts order).
- `choice.py` 616 - Mission 7 beat 7 - Two Channels: Vasile's offer, Maru's reply, then the choice.
- `colonel.py` 229 - Colonel Paie: the scarecrow easter egg on Bodi's farm.
- `draw.py` 38 - Mission 7 - placeholder frame: title, stage label and the advance hint.
- `farmyard.py` 2617 - Mission 7 top-down farmyard.
- `flow.py` 183 - Mission 7 - stage ladder, checkpoints, score cues and the outro handoff.
- `goat_rescue.py` 3729 - Mission 7 beat 2: Bodi's escaped goat.
- `m7_audio.py` 828 - Mission 7 sound design: the farm day, the warning, the night raid, the ending receiver.
- `maps.py` 112 - Mission 7 top-down farm: tile grid, palette and interaction points (beats 2 and 4).
- `meta.py` 100 - Mission 7 metadata and stage constants: Fallow Ground (skeleton).
- `minigames.py` 894 - Mission 7 farm minigames.
- `raid3d.py` 2816 - Mission 7 beat 5 - the raid: a third-person fight for Bodi's yard at night.
- `raid_brain.py` 683 - Mission 7 raid AI: the Guard sweep (riflemen, a dog, a truck gunner), the trucks, and the two allies, Bodi and Alex.
- `raid_hud.py` 166 - Mission 7 raid HUD: the top-down game's panels (via the M6 yard HUD helpers), a north-up farm minimap, speaker-colour...
- `raid_world.py` 878 - Mission 7 raid world: collision boxes, line of sight, the barn fire and the props.
- `systems.py` 34 - Mission 7 - per-frame update, dispatched by stage (placeholder stages: ENTER advances).

**`src/missions/m8/`**

- `__init__.py` 9 - Mission 8: The Call - re-export facade (load order = parts order).
- `draw.py` 28 - Mission 8 - frame: a 3D scene, or the stage's 3D beat.
- `flow.py` 278 - Mission 8 - stage ladder, checkpoints and the outro handoff.
- `m8_audio.py` 1221 - Mission 8 sound design: Route 12, the catwalk, the chase.
- `meta.py` 256 - Mission 8 metadata: identity, the two stage ladders and the beat scripts.
- `systems.py` 45 - Mission 8 - per-frame update, dispatched by stage: a 3D scene, or a beat.

**`src/missions/m8/duty/`**

- `__init__.py` 6 - Mission 8 Duty route ("Head of State"): films in `cutscenes/m8dutyfilms.py`, playable `mansion3d`, `flight3d`, `ridge3d`.
- `flight3d.py` 2762 - Mission 8 Duty - Phase 4: Last Flight (3D door-gunner chase).
- `flight_fx.py` 1269 - Mission 8 Duty - Last Flight 3D cabin, pintle LMG, rockets, AA trucks, and FX. (auto)
- `flight_set.py` 1249 - Mission 8 Duty - Dedicated night aerial chase corridor for Last Flight. (auto)
- `mansion3d.py` 2422 - Mission 8 Duty - Phase 2: The Mansion (3D third-person fight).
- `mansion_brain.py` 589 - Mission 8 Duty - Mansion 3D AI: Retardovici's guard across the estate, Bodi, Alex, and Andrei M.'s animated death.
- `mansion_env.py` 698 - Mission 8 Duty - Outer grounds, approach road, woodland, rolling foothills and distant capital skyline surrounding Retardovici'... (auto)
- `mansion_hud.py` 209 - Mission 8 Duty - Mansion HUD: floor-aware minimap, weapon panel, area cards, callouts, Andrei M.'s boss bar and the helicopter ...
- `mansion_props.py` 877 - Mission 8 Duty - Architectural doors and detailed furniture for Retardovici's estate. (auto)
- `mansion_set.py` 1340 - Mission 8 Duty - Retardovici's estate, the same house the Revenge funeral films (``epilogue3d.funeral``): plastered walls on a ...
- `mansion_world.py` 544 - Mission 8 Duty - the estate's solids, stacked floors and 3D sight lines.
- `ridge3d.py` 1800 - Mission 8 Duty - Phase 6: The Ridge (first-person scope finale).

**`src/missions/m8/revenge/`**

- `__init__.py` 3 - Mission 8 Revenge route: the Route 12 set (``set3d``), the trap and gantry fight (``trap3d`` over ``trap_world`` / ``...
- `beats.py` 185 - Mission 8 - 3D beats: the stage's lines as caption plates over the Route 12 set.
- `chase3d.py` 6062 - Mission 8 Revenge - phase 6: the tractor chase to the Kim Kim crossing.
- `chase_set.py` 2548 - Mission 8 Revenge - the tractor chase set: the back roads from Route 12 to the Kim Kim rail crossing, baked once (dawn sky via `night_sky(gpu=False)` + `stratus`).
- `epilogue3d.py` 637 - Mission 8 Revenge - phase 7: the epilogue, one 3D shot per line.
- `kill3d.py` 1048 - Mission 8: Vasile's last moment on the Route 12 gantry.
- `kill_cine.py` 469 - Mission 8 Revenge — GTA IV-style trigger-hijack assassination choreography. (auto)
- `set3d.py` 867 - Mission 8 Revenge - Route 12 in 3D, shared by the trap fight, the kill and the meet.
- `trap3d.py` 2559 - Mission 8 Revenge - phases 2 and 3: the Trap and the Gantry, one third-person scene.
- `trap_brain.py` 913 - Mission 8 Revenge - trap AI: Guard riflemen, breachers, elevated overwatch snipers, the interactive Guard truck and B...
- `trap_hud.py` 215 - Mission 8 Revenge - trap HUD: the raid's panels, tactical radar markers and callouts on a north-up Route 12 minimap d...
- `trap_world.py` 308 - Mission 8 Revenge - blocking solids, 3D sight lines and interactive hazards of the Route 12 set for the trap fight.

**`src/net/`**

- `__init__.py` 21 - net - multiplayer relay client.
- `client.py` 472 - Game-side client for the KRAPNET master server.
- `discovery.py` 50 - LAN auto-discovery for the master server.
- `match.py` 469 - A multiplayer match session: authoritative host + interpolating clients.
- `playit_agent.py` 220 - Bundled playit.gg agent for hosts without their own playit install.
- `portmap.py` 718 - Automatic router port forwarding (UPnP IGD + NAT-PMP), stdlib only.
- `protocol.py` 1554 - Wire protocol for the Acaristan multiplayer master server.
- `roomcode.py` 133 - Short, game-branded room codes for direct arena matches.
- `tcp_tunnel.py` 346 - Public raw-TCP tunnels for arena matches.
- `telemetry.py` 137 - Lightweight client-side telemetry for arena matches.
- `udp_transport.py` 45 - Small, bounded helpers for the real-time match datagram channel.

**`src/tools/`**

- `input_recorder.py` 61 - Dev-only gameplay input recorder (RPE6 Phase 0, replay baselines).
- `ko_playability_audit.py` 561 - Kill Order (Mission 3 Phase 5) playability audit - headless.
- `trailer_bot.py` 201 - Trailer bot - deterministic operator driver for cinematic capture.

**`src/ui/`**

- `__init__.py` 91 - Package ui - re-export facade.
- `arena_view.py` 1859 - Renderer for multiplayer arena matches.
- `arena_view3d.py` 606 - 2.5D renderer for multiplayer arena matches (HDR scoped off/restored).
- `credits.py` 491 - End credits sequence displayed after Mission 8's Call of Acaristan title card.
- `credits_football.py` 2324 - Credits background football match (Biribel vs Bodi): simulation, animations and 3D pitch.
- `egg666_3d.py` 361 - the Mission 1 safe-keypad "666" Easter egg as a lit 3D scene.
- `egg666_audio.py` 279 - procedural sound for the 3D "666" scare.
- `egg666_build.py` 340 - geometry for the 3D "666" scare: the vault, the ritual marks, the hanging lamp and the demon.
- `egg666_dir.py` 330 - the director of the 3D "666" scare: what happens at which frame.
- `egg666_fx.py` 138 - light halos, the PS2 grade and the crisp present for the 3D "666" scare.
- `egg666_post.py` 127 - screen effects for the 3D "666" scare.
- `hud.py` 1488 - HUD overlays: minimap, safe keypad, notebook inspection, desk notes.
- `kit.py` 206 - KRAPNET terminal style kit shared by the main menu and its sub-screens.
- `main.py` 994 - Split part. Public: `draw_menu_background`, `draw_menu`, `draw_menu_cursor`, `slot_panel_clicked`, `handle_menu_keydown`, `consume_keyboard_trigger`, `reset_keyboard_selection`
- `match_screen.py` 4881 - The in-game arena match: entry panel plus the live match runtime.
- `mission_complete.py` 606 - Physical KRAP Intelligence case dossier: manila folder, taped field photo, transcript slip, FORM KR-47.
- `mission_complete_3d.py` 1150 - Live engine3d dioramas for the MISSION_COMPLETE dossier exhibit frame.
- `mission_failed.py` 336 - Mission-specific failure terminals with bespoke procedural illustrations.
- `mp.py` 3411 - Split part. Public: `update_server_browser_animation`, `switch_mp_tab`, `open_dm`, `close_dm`, `send_dm_message`, `update_dm_state`, `draw_connections_panel`, `scroll_server_list`
- `mp3d.py` 343 - 3D kit for multiplayer: soldier rigs, guns and Outfitter portraits.
- `multiplayer_style.py` 375 - Read-only KRAPNET presentation.
- `pixfont.py` 349 - Pixel bitmap fonts for the radio UI (polish pass T6b).
- `radio.py` 772 - Radio transmission widget (polish pass T6, field-radio restyle T6b).
- `shop.py` 625 - The Outfitter - spend Acaribucks on the loadout you play the arena in.
- `speechbox.py` 350 - Speech box: the one in-person dialogue box and film caption for the game.
- `system.py` 1580 - Split part. Public: `draw_settings`, `draw_pause_menu`, `reset_death_animation`, `draw_death_screen`, `draw_black_ledger_death_screen`, `black_ledger_death_buttons_ready`, `draw_black_ledger_death_buttons`
- `tactical_hud.py` 89 - Shared tactical HUD styling & layout metrics (M1–M6): `HUD_MARGIN`, `PANEL_GAP`, `TACTICAL_THEME`, `draw_tactical_corners`, `tactical_panel_bg`, `place_minimap`.
- `upload_os.py` 3138 - Upload OS - a retro CRT terminal operating system for the evidence upload.
- `widgets.py` 320 - Split part. Public: `note_hover`, `consume_hover`, `clipboard_text`, `ModernButton`

## 21. Tools index (`tools/`, generated from module docstrings)

Scratch probes (`tools/_*.py`, about 23 `_m8_*` files) are skipped: they are throwaway capture scripts, not gates.

**`tools/`**

- `ae_api_snapshot.py` 175 - public API snapshot of ``src/engine`` (RPE6 Phase 2 gate).
- `ae_audit.py` 490 - RPE6 Phase 0 audit: static census of src/ and tools/ (read-only, stdlib only).
- `ae_bake.py` 112 - ae_bake - bake / check / lint content packs (RPE6 Phase 3, §6.5).
- `ae_bench.py` 148 - frame budget bench (RPE6 §6.22; Phase 6 exit evidence).
- `ae_bench3d.py` 108 - AE BENCH3D - 3D frame budget bench (RPE6 Phase 11 exit evidence).
- `ae_bench_scenes.py` 229 - Diagnostic 3D scene bench: M8 trap/chase/kill/mansion/flight/ridge, M7 raid, M6 yard/train (`--frames`, `--runs`, `--backend`); reports avg/p50/p99/max ms + fps. Not a CI gate.
- `ae_build_ak74.py` 651 - AE BUILD AK74 - the AK-74 (6P20) authored in code, with no GLB source.
- `ae_ci.py` 213 - RPE6 one-command CI (D10).
- `ae_d4_gate.py` 141 - D4 grep gate: no attribute stuffing on entity objects (RPE6 §2 D4, §6.4 acceptance).
- `ae_d4_replay_compat.py` 125 - proof that moving entity data into components kept behaviour (RPE6 Phase 5).
- `ae_d6_gate.py` 153 - D6 gate: one 2D render path (RPE6 §2 D6, §6.6; Phase 6).
- `ae_dialogue_check.py` 84 - ae_dialogue_check - Phase 7 dialogue gate: validate + data == legacy tables.
- `ae_dialogue_export.py` 91 - ae_dialogue_export - write the legacy conversation tables as ae.dialogue/1 data.
- `ae_draw_audit.py` 164 - ae_draw_audit - procedural-draw census per mission (RPE6 Phase 3, P3-M3).
- `ae_dump_components.py` 106 - component census of a running mission stage (RPE6 §6.4 acceptance).
- `ae_engine3d_parity.py` 80 - AE ENGINE3D PARITY - software-backend determinism evidence.
- `ae_export_ak74_glb.py` 473 - AE EXPORT AK74 GLB - the code-authored AK-74 written back out as a GLB source.
- `ae_flash_check.py` 61 - ae_flash_check - Phase 9 exit evidence: flash reduction caps the breach white-out.
- `ae_gauntlet.py` 112 - AE GAUNTLET - render everything once at offsets nobody tested.
- `ae_global_names.py` 130 - ae_global_names - unresolved global references in src (Phase 4 gate, A-001).
- `ae_golden.py` 550 - RPE6 golden-image harness (master prompt §9).
- `ae_hold_check.py` 139 - Weapon hold + arm self-collision gate for the 3D cutscenes.
- `ae_hud_census.py` 177 - ae_hud_census - HUD duplication census across missions (Phase 4 prep).
- `ae_import_akrifle.py` 113 - AE IMPORT AKRIFLE - the Guard/shared third-person rifle (assets/3D/ak-style-rifle.glb).
- `ae_import_car.py` 104 - AE IMPORT CAR - the Mission 2 civilian car (assets/3D/low-poly-car_green.glb).
- `ae_import_check.py` 105 - RPE6 import side-effect check (R7, §6.1 acceptance).
- `ae_import_dog.py` 151 - AE IMPORT DOG - the Mission 7 guard dog (assets/3D/dawg.glb) and its clips.
- `ae_import_duty_props.py` 140 - AE IMPORT DUTY PROPS - bakes `moneystack`, `ammo_crate`, `tactical_lmg`, `suppressed_pistol` for Mission 8 Duty.
- `ae_import_k93d.py` 326 - AE IMPORT K93D - the first authored 3D weapon asset (assets/3D/K93D.glb).
- `ae_import_krap_van.py` 200 - AE IMPORT KRAP VAN - the KRAP van (assets/3D/krap_van.glb).
- `ae_import_lmg.py` 116 - AE IMPORT LMG - Biribel's light machine gun in the M8 tractor chase (assets/3D/light_machine_gun.glb).
- `ae_import_m3_van.py` 109 - AE IMPORT M3 VAN - Volkov's armoured van (assets/3D/M3van.glb).
- `ae_import_m7rifle.py` 111 - AE IMPORT M7RIFLE - the allies' rifle in Mission 7 (assets/3D/M7Rifle.glb).
- `ae_import_mesh.py` 210 - AE IMPORT MESH - Blender/glTF/OBJ -> ae.mesh/1 asset (ADR-024).
- `ae_import_molotov.py` 118 - AE IMPORT MOLOTOV - the thrown molotov cocktail (assets/3D/low-poly-molotov.glb).
- `ae_import_pig.py` 85 - AE IMPORT PIG - the low-poly pig (assets/3D/low_poly_pig.glb).
- `ae_import_pistol.py` 95 - AE IMPORT PISTOL - the multiplayer service pistol (assets/3D/pistol_lowpoly.glb).
- `ae_import_sniper.py` 112 - AE IMPORT SNIPER - bolt-action suppressed sniper rifle (assets/3D/lowpoly_sniper_rifle.glb); reuses `ae_import_k93d._gltf/_scan/_cluster`.
- `ae_import_tractor.py` 99 - AE IMPORT TRACTOR - the Mission 7 tractor asset (assets/3D/TractorM7.glb).
- `ae_import_truck.py` 106 - AE IMPORT TRUCK - the Mission 7 Guard truck (assets/3D/IPA-army-truck.glb).
- `ae_import_workstation_props.py` 98 - Bake the six office/medical GLBs; no source model is loaded during play.
- `ae_layer_parity.py` 93 - Parity oracle for baked *chunk* layers (``game.art.<pack>.<name>`` adapters with ``bake_setup``): re-runs the mission...
- `ae_layer_probe.py` 173 - ae_layer_probe - can this camera-space painter become a baked world layer?
- `ae_level_check.py` 66 - validator: level JSON == legacy generator output (RPE6 P7).
- `ae_level_export.py` 102 - export the legacy mission grids to .level.json (RPE6 P7-M2).
- `ae_loop.py` 637 - RPE6 loop probe: drive the REAL app.py main loop headless and hash every frame.
- `ae_migrate_time.py` 156 - RPE6 B-001: move legacy wall-clock reads onto the engine timebase.
- `ae_mission0_check.py` 188 - AE MISSION0 CHECK - RPE6 Phase 10, D2 proof.
- `ae_narrow_star.py` 114 - ae_narrow_star - rewrite ``from core.config import *`` into explicit imports (A-001, Phase 4).
- `ae_new_mission.py` 462 - scaffold a new RPE6 mission (Phase 10, §7/D2).
- `ae_normalize.py` 263 - RPE6 Phase 0 item 7: line-ending / encoding normalisation with proofs (R14, B-003).
- `ae_package.py` 99 - AE PACKAGE - build the distributable game zip.
- `ae_proof3d.py` 158 - AE PROOF3D - render the fixed Phase 11 proof scenes to PNGs.
- `ae_proof_sheet.py` 78 - AE PROOF SHEET - side-by-side before/after sheet for Phase 11 steps.
- `ae_reexport_check.py` 103 - ae_reexport_check - who pulls star-imported names THROUGH another module?
- `ae_replay.py` 293 - RPE6 replay baseline + determinism check (master prompt §6.17, Phase 0 item 9, D8).
- `ae_replay_check.py` 88 - RPE6 Phase 9 exit tool: engine-save snapshots reproduce replay state.
- `ae_set3d_check.py` 64 - ae_set3d_check - Phase 8 set gate: validate + build every .set3d.json.
- `ae_star_imports.py` 140 - ae_star_imports - inventory of ``from core.config import *`` users (A-001 prep, Phase 4).
- `ae_text_check.py` 351 - string-table validation and text fit (RPE6 Phase 4, 6.13).
- `ae_textures_gen.py` 91 - AE TEXTURES GEN - deterministic palette textures (RPE6 Phase 11 step 9).
- `ae_timeline_check.py` 114 - ae_timeline_check - Phase 8 timeline gate: validate + data == legacy tables.
- `ae_timeline_edit.py` 93 - ae_timeline_edit - the Phase 8 camera/track key editor (CLI form).
- `ae_timeline_export.py` 103 - ae_timeline_export - write the legacy cutscene shot lists as ae.timeline/1 data.
- `ae_validate.py` 73 - AE VALIDATE - load every game data file through its public loader.
- `ai_bundle.py` 84 - Bundle whole files or line slices (`path:start-end`) into one paste-ready block for an external chat AI.
- `ai_bundle_app.py` 1250 - AI Bundle - paste an AI's file request, get the requested files on the clipboard (`apps/AIBundle.exe`).
- `ak74_preview.py` 326 - AK-74 preview - renders the code-authored weapon so it can be eyeballed.
- `assemble_final_trailer.py` 811 - Post-production assembler for CALL OF ACARISTAN.
- `bake_m5_sprites.py` 16 - Compatibility wrapper: the Mission 5 bake moved to the generic pipeline.
- `build_all_sprites.py` 54 - Rebuild every generated art asset in one go (Polish T7).
- `build_apps.py` 64 - Build the standalone desktop apps in tools/ into self-contained exes under `apps/` (`AIBundle`, `GLBInspector`, `PasteApply`).
- `build_code_pdf.py` 1197 - build_code_pdf.py High-Density Archival Monolith GUI & CLI.
- `build_code_txt.py` 309 - build_code_txt.py Selective TXT code bundle (.py, .bat, .json, .md, configs...): pick files, pick folder, get TXT onl...
- `build_ost.py` 62 - Render the Call of Acaristan OST (tools/ost/album.py).
- `build_ost_videos.py` 222 - Render the OST music videos: one seamless 3D loop per album track.
- `build_radio_cache.py` 63 - Pre-build the radio-FX voice cache (assets/voice/_radio_cache).
- `build_sfx_stem.py` 520 - render trailer_sfx_stem.wav from captured foley logs.
- `build_windows.py` 102 - Build the Windows game as a PyInstaller --onedir bundle (no admin needed).
- `cast_lineup.py` 91 - 3D cast line-up: python tools/cast_lineup.py [body/face] [out.jpg] [key ...]
- `cast_sheet.py` 154 - Cast sheets: the 2D cutscene figures (figure_kit) beside their 3D rigs.
- `check_boundaries.py` 148 - RPE6 boundary lint (master prompt §5.3, D1).
- `convert_voice_ogg.py` 62 - Convert assets/voice/**/*.wav to OGG Vorbis in place (RPE6 housekeeping, 2026-10-14).
- `debug_stem.py` 32 - Standalone timing run of mp_trailer_assemble.render_foley_stem.
- `dev_panel.py` 1439 - clickable dev control panel for jumping into missions.
- `download_bore.py` 25 - Fetch the pinned official Windows x64 bore release for PyInstaller builds.
- `download_playit.py` 25 - Fetch the pinned official playit.gg agent (playitd) for PyInstaller builds.
- `egg666_shots.py` 85 - Headless shots of the 3D "666" scare.
- `engine3d_check.py` 118 - GPU vs software renderer check on the real M2 ambush film.
- `export_m5_audio.py` 46 - Export the exact procedural M5 mix for audition; no app launch/saves.
- `finale_compare.py` 59 - Side-by-side probe: M2 ambush film (sniper3d) vs M5 finale (m5shadow3d).
- `finale_gait_check.py` 46 - M5 finale gait check: Maru timing, footstep contact times, world foot drift.
- `finale_probe.py` 52 - Render M5 finale frames (optionally from custom cameras) into a JPEG contact sheet.
- `gen_barrel_obj.py` 70 - Generate assets/import/barrel.obj - a low-poly barrel (10 sides, bulged profile, two metal bands) as the Step-11 impo...
- `glb_inspector.py` 1635 - GLB Inspector - desktop viewer for .glb / .gltf files (`apps/GLBInspector.exe`).
- `golden.py` 125 - golden-image regression gate for the reworked renderer.
- `itch_push.py` 94 - Push a built game to itch.io with butler (the official itch upload CLI).
- `k9_pickup_check.py` 142 - Headless regression checks and optional preview for the K-9 pickup.
- `m1_hall_probe.py` 118 - Diagnostic probe: can the player actually cross commander K's hall (rows 21-25)?
- `m1_td3d_shots.py` 57 - Render Mission 1 top-down frames in 2.5D (and 2D with ACA_TD_2D=1).
- `m2_fire_probe.py` 113 - Time Mission 2 frames after the tanker blast (fire cost probe).
- `m2_td3d_shots.py` 80 - Render Mission 2 top-down frames in 2.5D (and 2D with ACA_TD_2D=1).
- `m3_broadcast_preview.py` 36 - Capture the M3 broadcast bridge, including action endpoints and long holds.
- `m3_ko_preview.py` 33 - Capture Kill Order's four directed 3D shots on either backend.
- `m3_staging_preview.py` 39 - Capture M3's service bridge: python tools/m3_staging_preview.py [--backend software].
- `m3_td3d_shots.py` 83 - Render Mission 3 frames in 2.5D (and 2D with ACA_TD_2D=1).
- `m4_gameplay_video.py` 452 - Record a bot-played Mission 4 gameplay video (2.5D) to MP4.
- `m4_intro_patch.py` 61 - Replace the M4 intro shot-list table in missions/m4/meta.py.
- `m4_probe.py` 24 - Probe the audio sound registry for names the M4 intro might reuse.
- `m4_td3d_shots.py` 110 - Render Mission 4 frames in 2.5D (and 2D with ACA_TD_2D=1).
- `m5_cinematic_polish_check.py` 76 - Regression evidence for the M5 noir polish; safe isolated preview only.
- `m5_contact_sheets.py` 52 - Build labelled contact sheets + automatic frame stats from previews/m5_encounter_review.
- `m5_cut_check.py` 32 - Round-2 M5 cutscene check: renders every m5x_ take (3D, then 2D fallback).
- `m5_draw_audit.py` 14 - Compatibility wrapper: the per-mission draw census is tools/ae_draw_audit.py.
- `m5_dump.py` 18 - (no docstring)
- `m5_encounter_review.py` 173 - Deterministic M5 preview suite.
- `m5_ending_stage_check.py` 184 - Ending staging/weapon regressions and native-size visual probes; safe saves.
- `m5_feedback_check.py` 170 - Focused M5 feedback regressions and visual evidence, without touching saves.
- `m5_finale_cut_check.py` 121 - Focused check for retiring the M5 finale without losing campaign completion.
- `m5_fx_check.py` 68 - M5 FX checks: reduced motion zeroes handheld/shake/roll; 2D fallback still works.
- `m5_gauntlet_cycle.py` 169 - M5 visual gauntlet - one full cutscene render cycle at delivery resolution.
- `m5_gauntlet_sheet.py` 51 - Compact WebP contact sheet for remote VLM review.
- `m5_gauntlet_shots.py` 124 - M5 gauntlet: render every Mission 5 surface we review (top-down stages, sprite close-ups, every 3D cutscene take + 2D...
- `m5_harbour_art_check.py` 59 - M5 harbour pass guard: the cubical cast and the choreography are pinned, art is validated.
- `m5_laser_stair_check.py` 58 - M5 laser integration and stair landing regression, both renderer backends.
- `m5_probe.py` 54 - render M5 cutscene frames headless for visual review.
- `m5_r2_check.py` 62 - Round-2 M5 headless check: builds stages, draws a few frames, saves PNGs.
- `m5_rifle_clearance.py` 55 - Weapon clearance against actual torso/head/pelvis box meshes, plus grip reach.
- `m5_shadow_check.py` 280 - Fresh M5 3D finale: geometry, timing, actual app player and save handoff.
- `m5_sheet.py` 42 - Contact sheet for review: python tools/m5_sheet.py out.jpg name1 name2 ...
- `m5_shots.py` 66 - M5 3D cutscene stills + timing: python tools/m5_shots.py OUT_DIR [scene_prefix]
- `m5_sprite_review.py` 45 - Montage of selected baked M5 sprites for review.
- `m5_stair_room_check.py` 73 - Regression: interiors cover the frame and both stair actors remain visible.
- `m5_td3d_shots.py` 55 - Render Mission 5 frames in 2.5D (and 2D with ACA_TD_2D=1).
- `m5_topdown_frame.py` 55 - Render one M5 top-down frame (the quarter night) as the house-style target.
- `m5_view_export.py` 47 - Pack review images for remote viewing: prints one JSON line per image {name, b64 JPEG}.
- `m6_ammo_check.py` 80 - Focused headless regression for the M6 K-9 supply ladder.
- `m6_bench.py` 181 - M6 3D scene frame bench + profile (diagnostic, not a CI gate).
- `m6_diag.py` 180 - One-command M6 3D performance diagnostic - run this on the stuttering PC.
- `m6_halo_sheet.py` 120 - B8 tuning sheet: one M6 sodium lamp at 5/15/40/80 m, four depth cases.
- `m6_hitch.py` 163 - Hitch hunter for the M6 3D scenes.
- `m6_layout_probe.py` 93 - M6 layout probe: every authored coordinate must land on open floor.
- `m6_loop_probe.py` 126 - Whole-game frame-interval probe for a dev-booted M6 scene.
- `m6_melee_strip.py` 82 - Melee parity check: render one M6 K-9 swing frame by frame.
- `m6_phases.py` 107 - Phase-level timing of the M6 train / yard draw (GL path).
- `m6_prof.py` 66 - (no docstring)
- `m6_shots.py` 416 - M6 3D film + interactive train stills.
- `m6_snow_probe.py` 113 - Customs snow probe (dev only, not a CI gate).
- `m6_td3d_shots.py` 53 - Render Mission 6 frames in 2.5D (and 2D with ACA_TD_2D=1).
- `m6_topdown_shots.py` 156 - Top-down M6 review stills (customs / no-man's-land / rail yard).
- `m7_prof.py` 87 - Profile the Mission 7 raid frame headless.
- `m7_route_probe.py` 28 - Collision and safe-dismount regression for the Mission 7 tractor.
- `m8_chase_diff.py` 25 - Compare consecutive chase frames: how much does the background actually change?
- `m8_chase_shots.py` 61 - Render the M8 tractor chase at points along the route, for eyeballing the set.
- `m8_descent_shots.py` 92 - Render the M8 descent film frames and the first chase frame, and check the handoff.
- `make_art_pack.py` 1249 - author assets/art/*.png (phases 1, 2, 4 art).
- `make_short_branded.py` 217 - branded 9:16 vertical Short from the final master.
- `make_short_clean.py` 101 - 9:16 vertical Short from the final master.
- `make_station_sprites.py` 144 - author the hero-interactable sprites.
- `map_assets3d.py` 213 - Keep docs/ARCHITECTURE_MAP.md section 8.1 in sync with assets/3D/.
- `mp_arena_duo.py` 101 - Launch TWO full game windows already sitting in the multiplayer arena.
- `mp_bot.py` 132 - Headless fake player, for testing multiplayer on ONE PC.
- `mp_choreo_probe.py` 269 - gate the MP trailer fight headlessly before capturing.
- `mp_host.py` 285 - Self-hosted KRAPNET server for Call of Acaristan.
- `mp_host_main.py` 23 - PyInstaller entry point for the self-hosted lobby EXE.
- `mp_join.py` 196 - Join a friend's Call of Acaristan lobby and chat.
- `mp_match.py` 429 - Play a real multiplayer arena match.
- `mp_net_soak.py` 572 - Headless arena network test with optional TCP and UDP impairment.
- `mp_remaster.py` 36 - Re-master audio only: reuse the kept premix.wav, re-run normalise + mux.
- `mp_server.py` 533 - Standalone KRAPNET master server for Call of Acaristan.
- `mp_trailer_assemble.py` 852 - post-production assembler for the MULTIPLAYER announcement trailer.
- `mp_trailer_assemble_tiktok.py` 867 - 9:16 TikTok cut of the multiplayer announcement.
- `mp_trailer_capture.py` 2002 - REAL multiplayer arena footage for the announcement trailer.
- `oilrig_preview.py` 120 - Off-screen preview of the oil-rig strike cinematic (missions.walking_attack3d).
- `overlay_cleanup.py` 69 - Tidy a project root after pasting the slim overlay zip over an older checkout.
- `paste_apply.py` 1509 - Paste Apply - apply an AI-written change set from a paste, no agent needed (`apps/PasteApply.exe`; rebuild with `build_apps.py` after edits).
- `patch_m7_raidin.py` 103 - One-shot data patch for the M7 raid-in film caption - run from the repo root:
- `preflight_bot_test.py` 68 - Offline pre-flight: exercise GridNav + ArenaBot + foley payloads against a bare ArenaSim (no sockets, no capture) to...
- `preview_mission_complete.py` 140 - Render/test every mission-complete case dossier; --show opens a save-free gallery.
- `preview_mission_failed.py` 166 - Render/test all failure terminals; --show opens a safe, save-free gallery.
- `publish_update.py` 226 - Publish an update package and manifest for the Call of Acaristan Launcher.
- `record_fresh_action.py` 1007 - clean standalone combat capture.
- `render_ko_video.py` 324 - Headless cinematic trailer bot, PLAN_2 cut.
- `render_m4_ending.py` 205 - Render the real M4 cutscene player safely, without importing app's loop.
- `render_m5_ending.py` 66 - Render M5 with the production cutscene player, using the safe M4 capture kit.
- `render_m5_shadow.py` 75 - Capture the production M5 finale at 30 fps with native ambience/foley.
- `render_m5_stair.py` 82 - Export the complete updated M5 stair shot with its production sound cues.
- `render_m7_feedback.py` 193 - Render review shots for the Mission 7 feedback pass (software renderer).
- `render_m7_previews.py` 36 - (no docstring)
- `render_trailer.py` 762 - 75-90s MP4 game trailer (headless real gameplay).
- `render_trailer_v2.py` 626 - cinematic finish wrapper over render_trailer.py.
- `shot_fail_screens.py` 35 - Polish pass T9 evidence: render the Mission Failed screen for M1-M5.
- `shot_m5x.py` 57 - Polish pass evidence helper: render M5X 3D cutscene frames to PNG.
- `shot_outfit.py` 134 - Polish pass Task 5 evidence: Biribel's M5 Guard kit in every view.
- `shot_radio.py` 207 - Polish pass Task 6 evidence: the radio transmission widget in every mission.
- `shot_speechbox.py` 137 - Evidence shots for the shared speech box (``ui.speechbox``).
- `shot_weapon_grid.py` 108 - Polish pass Task 4: weapon-attachment verification grid.
- `slim_tree.py` 222 - remove dead weight from the project root (dry run by default).
- `smoke_test.py` 12723 - Public: `EmptyKeys`, `run_check`, `run_import_check`, `clear_screen`, `check_menu_draw`, `check_settings_draw`, `check_multiplayer_opens_on_server_browser`, `check_host_is_taught_how_to_host`
- `test_m7_pig.py` 83 - Focused geometry and raid gait regression checks; run from the project root.
- `test_m7_pig_death.py` 185 - The pig in the 3D raid, and what it costs.
- `test_multiplayer_ui.py` 88 - Small presentation regression suite; no live networking or external service.
- `test_oilrig_collapse.py` 137 - Geometry and effect regressions for the rig collapse repair.
- `test_tcp_tunnel.py` 79 - Fast stdlib-only tunnel regression tests (no pygame or internet required).
- `tex3d_draw.py` 510 - Draws the M6 3D pixel textures (assets/tex3d/<name>.png) from the 2D palette.
- `tex3d_draw_m7.py` 397 - Draws the M7 farm 3D pixel textures (assets/tex3d/m7_<name>.png) from the 2D farm palette (src/cutscenes/m7palette3d....
- `van3d_shot.py` 26 - Render the 3D van_exterior take to PNGs: python tools/van3d_shot.py [t_ms ...]
- `view_cast3d.py` 119 - Interactive 3D character viewer (defaults to andrei_m).
- `vo_batch.py` 1365 - Batch packer, silence/DP auto-splitter, unrenamed-drop ingest, reference-stitcher, Colab Qwen3-TTS kit/import and manifest sync for AI Studio voice-over.
- `voice_audit.py` 545 - Voice-line audit (polish pass T1).
- `walk_fp_shots.py` 81 - Render stills of the walking-sim first-person reward cutscenes.
- `wrap_audit.py` 152 - Every player-facing line through the shared text widgets (wrap/fit audit).
- `walk_probe.py` 142 - framed shots + draw-cost probe for the walking sim.
- `walk_td3d_shots.py` 50 - Render walking-sim frames in 2.5D (and 2D with ACA_TD_2D=1).
- `zip_project.py` 470 - Zip this project into a single archive, optionally uploading it to Pixeldrain.

**`tools/ost/`**

- `album.py` 1366 - Call of Acaristan - Original Soundtrack (20 tracks; 13-20 each with unique meters, kits, harmony and motifs).
- `mv.py` 1297 - OST music videos: one short, loopable 3D scene per album track (engine3d, GL).
- `synth.py` 978 - Small numpy synth for the Call of Acaristan OST (+ `cello`, `vibra`, `analog_lead`, `upright_bass`, `sub_kick`, `ind_snare`, `brush`, `shaker`, `clave`).

**`tools/sprites/`**

- `compare_shots.py` 47 - stitch T7 before/after shots side by side.
- `fx.py` 174 - Mission 2 tanker-blast aftermath as sprites (Polish T7).
- `inventory.py` 212 - Procedural-art inventory (Polish Task 7, step 1).
- `kit.py` 241 - shared machinery for the tools/sprites/<family>.py generators.
- `m1_street.py` 399 - Mission 1 street band furniture (WP4) as authored sprites.
- `mission_failed.py` 392 - Bespoke, entirely code-drawn mission-failure vignettes.
- `palette.py` 121 - the locked house palette shared by every tools/sprites generator.
- `portrait_refs.py` 79 - check the radio portraits against the cutscene cast.
- `portraits.py` 1156 - radio caller-ID portraits (polish pass T6b).
- `props.py` 278 - Mission 2 story props + the upload terminal as sprites (Polish T7).
- `t7_probe.py` 155 - before/after shots + draw-time probe for Polish T7.
- `vehicles.py` 463 - Mission 2 road vehicles as authored sprite sheets (Polish T7).

**`tools/trailer3d/`**

- `common.py` 401 - Shared trailer helpers: renderer setup, camera keys, 2D light/rain/grain FX, letterbox + text.
- `music_cut.py` 125 - Cut 'Shell Ghost' (Soundridemusic) to the 80 s trailer timeline.
- `props3d.py` 352 - Low-poly trailer props built from engine3d boxes/prisms (y up, metres).
- `render.py` 142 - Render the cinematic trailer.
- `sfx.py` 301 - Synthesised sound design for the cinematic trailer, laid onto the music+VO mix.
- `shots.py` 1367 - The trailer's shots.
- `thumbnail.py` 176 - YouTube thumbnails (1280x720) composed from real trailer frames.
- `vertical.py` 235 - 9:16 TikTok / YouTube Shorts / Reels cut of the cinematic trailer.
- `vo_mix.py` 202 - Place the trailer narration on the 80 s music cut and mix it.

**`tools/trailer_25d/`**

- `capture.py` 74 - Gameplay clips for the 2.5D announcement trailer (TVA 1 broadcast).
- `capture_m4.py` 17 - Mission 4 2.5D clip for the announcement trailer: the m4_gameplay_video bot run with its captions and title cards swi...
- `capture_mp.py` 53 - Multiplayer arena clip (2.5D) for the announcement trailer.
- `capture_tilt.py` 64 - The switch shot: one continuous M1 bot run that starts in the flat 2D view, flips to 2.5D and tilts the camera from s...
- `capture_wave.py` 66 - The switch shot, recorded twice per tick: one M3 bot run drawn in the flat 2D view and in 2.5D on the same sim frame,...
- `render.py` 1195 - TVA 1 broadcast: the 2.5D announcement trailer.
- `sets.py` 724 - 3D sets for the TVA 1 broadcast: studio desk, palace podium with the depth lever, the block flat, the neighbour's win...
- `shorts.py` 353 - Four vertical shorts (1080x1920, 30 fps) cut from the 2.5D announcement.
- `thumbnail.py` 183 - YouTube thumbnail for the 2.5D announcement (1280x720).

**`tools/trailer_rpe6/`**

- `dark.py` 573 - Dark story trailer for Call of Acaristan, cut to "Dark Cello Horror Trailer Music".
- `dark_films.py` 618 - New staged scenes for the dark trailer, built on the Mission 7 farm set.
- `dark_short.py` 304 - Vertical 1080x1920 Short of the dark trailer, and thumbnails for both.
- `render.py` 1098 - RPE6 engine trailer for Call of Acaristan: the engine and the game, no story.
- `render_m7.py` 311 - RPE6 trailer, Mission 7 cut: the 80 s engine trailer with Fallow Ground in it.
- `score.py` 160 - Sound for the RPE6 trailer: "Shell Ghost" (Soundridemusic), placed so its first hit lands on the voxel logo, under sy...
- `shorts.py` 573 - Vertical 1080x1920 cuts of the RPE6 trailer for TikTok / YouTube Shorts.



## 22. Tests index (`tests/`)

Run `python -m unittest discover -s tests/unit -t .` (or `pytest tests/unit`). Baselines are listed in §18.

**`tests/`**

- `__init__.py` 0 - (no docstring)

**`tests/unit/`**

- `__init__.py` 0 - (no docstring)
- `_helpers.py` 22 - Shared test setup: put ``src`` on sys.path and keep SDL headless.
- `_path.py` 7 - (no docstring)
- `test_anim_props.py` 63 - Phase 11 step 10: flicker is a deterministic closed form; set fields written as timeline expressions animate with the...
- `test_app_boot_crash.py` 128 - engine.core.App: headless boot, service wiring, crash report (§6.1 acceptance).
- `test_ai_bundle_app.py` 266 - tools/ai_bundle_app.py: request parsing, file reading, slicing, settings, CLI.
- `test_art_cache.py` 45 - art_cache.get_plate_bg: the shared M4/M5 "status plate" chrome.
- `test_assets_registry.py` 368 - engine.assets Phase 3: manifest schema, registry chain + cache + ref-counts, bake/check hashing, lint, hot reload (wa...
- `test_bloc3d.py` 179 - Phase 5: the Bloc landmarks and Cyrillic signage build sane boxes.
- `test_cast_shadows.py` 58 - Phase 11 step 7 (ADR-023): baked cast shadows - occluded faces darken, open faces do not, quality 0 disables the bake.
- `test_clock.py` 172 - engine.core.Clock: fixed-step semantics, identity with the legacy FixedStepClock (ADR-004).
- `test_devtools.py` 100 - RPE6 Phase 10 (§6.19): debug overlay / inspector data builders + console commands.
- `test_egg666.py` 268 - Tests for the 3D "666" safe-keypad scare (ui/egg666_*.py).
- `test_engine_ai.py` 253 - engine.ai: behaviour tree preemption and memory, sight reaction and forgetting, noise muffling, squad radio/tokens/cl...
- `test_engine_boot.py` 72 - App.boot display ownership (ADAPTER A-001).
- `test_engine_collision.py` 150 - engine.collision: box rays and segments agree with brute force, and grid nav routes round walls, through gaps and nev...
- `test_engine_collision_mesh.py` 79 - engine.collision.mesh: hitboxes follow the mesh's triangles, not a box around it, and a placed mesh uses the renderer...
- `test_engine_core.py` 177 - Unit tests for engine.core (stdlib unittest; run: python -m unittest discover -s tests/unit -t .).
- `test_engine_dialogue_box.py` 89 - engine.ui.std.dialogue_box (Phase 4): theme injection, slide ownership.
- `test_engine_level_dialogue.py` 144 - engine.level + engine.dialogue kernels: load/validate, Tiled import, runner conditions/effects (RPE6 Phase 7).
- `test_engine_render2d.py` 310 - engine.render2d kernel: queue order, drawables, rotation cache, camera, static chunks, post-FX parity (RPE6 Phase 6).
- `test_engine_settings_save_input.py` 142 - engine.settings / engine.save / engine.input kernels (RPE6 Phase 9).
- `test_engine_shims.py` 72 - A-006 shims: the legacy paths re-export the engine implementations unchanged.
- `test_engine_text.py` 213 - engine.text Phase 4: string tables + `T()`, font registry + glyph coverage, layout (measure/wrap/ellipsize/check_fit/...
- `test_engine_timeline_set3d.py` 98 - engine.timeline + engine.render3d kernels: expressions, sampling, set building (RPE6 Phase 8).
- `test_engine_ui.py` 142 - engine.ui Phase 4: Theme + the standard widgets, drawn headless.
- `test_engine_world.py` 233 - engine.world kernel: registry, storage, views, queries, scheduler phases, prefabs (RPE6 Phase 5).
- `test_events_log_services.py` 140 - engine.core: EventBus (§6.3), Log (§6.23), Services and Settings (§6.1).
- `test_faces3d.py` 78 - Phase 11 step 8: expressions rebuild only the face, mouth flap is a deterministic closed form, look-at clamps, mouth...
- `test_frame_pacer.py` 62 - core.frame_pacer: whole fixed steps per frame, rate drop on slow frames, never below 30 fps, lone spikes keep the rate.
- `test_game_dialogues.py` 74 - game.dialogues converter: node chain -> legacy beat dicts (RPE6 Phase 7).
- `test_game_world_bridge.py` 228 - game.world bridge (RPE6 Phase 5, D4): ensure/get, roster reset + removed-tag policy, WalkCycle.advance.
- `test_gl_composite.py` 113 - GL renderer item-queue regression (owner-hardware crash, M5 finale).
- `test_hold.py` 71 - Public: `HoldTests`
- `test_ik.py` 124 - engine3d.ik: analytic arm/leg IK and the shouldered rifle hold land on their targets as measured by the rig's own for...
- `test_m3_broadcast3d.py` 95 - Broadcast bridge framing, settled blocking, registry routing and seeking.
- `test_gameplay_sweep.py` 163 - Gameplay sweep regressions: M8 trap checkpoint ammo, kiosk gate Bodi post, full-reserve looting, mansion cross-floor revive, M1-M5 pickups at full.
- `test_m3_door_orientation.py` 49 - M3's visual door panels follow the wall, including every double leaf.
- `test_m3_ko3d.py` 229 - Kill Order 3D routing, seekable action, stair support and cover geometry.
- `test_m3_molotov_gate.py` 48 - M3 must not create un-simulated molotovs from the shared input handler.
- `test_m3_staging.py` 180 - M3's first 3D bridge: deterministic seeking, prop contact and fallback.
- `test_m5_ending.py` 179 - M5 finale regressions.
- `test_m5_finale_audio.py` 220 - Focused M5 sound/lifecycle regressions, without starting app or saves.
- `test_m6_campaign.py` 1132 - Mission 6 campaign regressions.
- `test_m7_campaign.py` 353 - Mission 7 campaign regressions.
- `test_m8_chase_gun.py` 327 - The mounted LMG must never pass through Biribel in the tractor chase.
- `test_m8_duty_mansion.py` 128 - M8 Duty mansion security room: workstation/desk alignment, interior-only Andrei trigger, player-shot vs misfire and cash-burst bounds, dynamic rack surge on software.
- `test_m8_chase_scenery.py` 62 - The trailer's rearward view must change as the tractor crosses four regions.
- `test_m8_chase_traffic.py` 230 - The tractor chase traffic must be solid, enter from off-camera, and swerve around wrecks only when the steering limit...
- `test_m8_trap_mechanics.py` 129 - M8 trap scene: the plaza fight's new mechanics.
- `test_mission_complete_ui.py` 191 - MISSION_COMPLETE physical case-dossier screen (ui/mission_complete.py).
- `test_mathx_profiling.py` 51 - engine.core.mathx and Profiler.
- `test_mesh_import.py` 134 - Phase 11 step 11 (ADR-024): the importer converts OBJ/glTF into ae.mesh/1 with palette snapping + triangle budget; th...
- `test_phase1_rng_imports.py` 58 - Phase 1 checks: legacy rng stream (R6) and m3 import side effects (B-010).
- `test_post3d.py` 79 - RPE6 Phase 11 step 5: cinematic post stack (cutscenes.post3d).
- `test_presets.py` 71 - RPE6 Phase 11 step 1: lighting preset resolution (engine.render3d).
- `test_render3d_p11.py` 57 - RPE6 Phase 11: local lights, contact shadows, baked AO (data -> bridge).
- `test_render_adapters.py` 259 - Phase 6 peel-off twins are pixel-identical to the legacy painters they replace (RPE6, ADR-017).
- `test_revive3d.py` 135 - Shared 3D ally-revive controller: proximity cues, four-stage pull, world-space IK clasp convergence, early-release and post-revive follow-through.
- `test_rng.py` 85 - engine.core.rng: named streams are independent, seeded, snapshot-able (R6, B-002).
- `test_scene_mirror.py` 104 - core.scene_mirror (A-005): the legacy FSM replayed onto an engine SceneStack.
- `test_scene_stack.py` 161 - engine.scene: lifecycle, overlay/passthrough dispatch, deferred mutations, trace (§6.2).
- `test_scene_types.py` 152 - engine.scene.CutsceneScene / InspectScene (§6.2) and the mirror's scene factory (A-007).
- `test_scenery3d.py` 101 - Imported scenery budgets, grounded placement, live displays and fallbacks.
- `test_textures3d.py` 85 - Phase 11 step 9: palette textures load through the bridge, UV payloads attach at quality >= 1 only, and pass through...
- `test_timeline_edit_scene.py` 58 - Phase 8 tooling surface: ae_timeline_edit round-trip + CutsceneScene.from_timeline.
- `test_voice_timing.py` 163 - Voice clip timing must not depend on SDL's decoded length (asset diet, 2026-10-14).
- `test_weather3d.py` 76 - Phase 11 step 6: weather is a closed-form, seeded, quality-gated function of (prims, t) - same inputs, same sprite ca...
