---
Task ID: refactor-1
Agent: main (Super Z)
Task: Implement shared helpers for cross-mission mechanics and port both Mission 1 (mission.py) and Mission 2 (mission2.py) to use them, eliminating the per-mission drift documented in the prior mechanics comparison.

Work Log:
- Read effects.py, audio.py, ui_hud.py, player.py, weapons.py, config.py, state.py to understand existing signatures and shared state.
- Read the relevant sections of mission.py (camera ~917-927, melee ~950-993, bullets ~994-1078, particles ~884-893, HUD ~2255-2275 + 2346-2361, bullet render ~1886-1896) and mission2.py (camera ~3913-3976, melee ~3348-3362, bullets ~3522-3584, _burst ~782-788, HUD ~7042-7047 + 7413-7426, bullet render ~8273-8275).
- Installed pygame into the venv for runtime testing.

Helpers implemented:
- effects.shake(amount): added docstring emphasizing max-clamp semantics; existing implementation already correct.
- effects.burst(x, y, color, count, speed_mul, life_min, life_max, jitter): new unified particle-burst helper respecting SETTINGS.particle_density. Replaces M1's raw Particle() loops and M2's local _burst().
- effects.play_impact(name, source_pos, base_volume, listener): new 3D-audio wrapper that auto-detects the listener (STATE.player) and degrades to flat playback if player is dead. Restores M1's spatial audio behavior in M2.
- camera.update_camera(target, map_w, map_h, focus_factor, handheld_jitter_timer, factor_fn): new shared camera function with first-frame snap, recoil kick decay, swept shake update, map-bounds clamp on desired position (M2's correct approach), and optional per-frame factor_fn for M2's sniper-stage smoothstep easing.
- camera.reset_camera_state(): clears the camera_initialized flag.
- camera.collide_bullet_walls(b, solid_walls): swept clipline collision; replaces M1's point-sample AABB (which could tunnel through thin walls) and M2's inline clipline loop.
- camera.draw_bullets(surface, bullets, cam_x, cam_y, with_glow): unified bullet renderer with optional glow halo. Restores M1's glow in M2.
- player.resolve_melee(player, enemies, solid_walls, blood_color): unified melee resolver with range 52, Â±60Â° cone, wall-LOS check, damage 78, 10 particles, shake 8. Replaces M1's inline block (range 48, dmg 80, 8 particles) and M2's inline block (range 55, no cone, no LOS, dmg 75, 12 particles).
- ui_hud.draw_objective_panel(surface, text, x, y): unified objective banner (520 px wide, "OBJECTIVE:" prefix prepended). Replaces M1's 450 px inline panel and M2's 620 px inline panel.
- ui_hud.draw_pinned_radio(surface, pinned_texts, x): unified pinned-radio renderer at bottom-left, capped to last 4 messages. Replaces M1's "all messages bottom-left" and M2's "last 2 top-right".

State changes:
- state.py: added STATE.camera_initialized flag (set False on init, set True by camera.update_camera on first frame).
- mission.py: added MAP_W/MAP_H constants derived from mission1_map (30 cols Ã— 24 rows).
- mission.py start_mission: resets STATE.camera_initialized = False and STATE.cam_kick_x/y = 0.0 on every mission (re)start.
- mission2.py start_mission2: sets STATE.camera_initialized = True after _snap_camera_to (since the camera is pre-snapped).
- mission2.py: STATE.show_minimap changed from False to True (was a bug â€” players thought the minimap was broken).

Ported call sites in mission.py:
- Camera update at ~917-927 â†’ camera.update_camera() with map_w=MAP_W, map_h=MAP_H.
- Melee block at ~950-993 â†’ player.resolve_melee() (also added STATE.melee_hit_done = False reset at swing end, which M1 was missing).
- Bullet/wall collision at ~1000-1016 â†’ camera.collide_bullet_walls() + effects.burst() + effects.play_impact().
- Bullet/volkov + bullet/commander + bullet/enemy particle loops â†’ effects.burst().
- Bullet/player-hit shake â†’ effects.shake(6) (was direct assignment).
- Player death feedback at ~884-893 â†’ effects.shake(22) + effects.burst(48, speed_mul=1.6) (was 50 raw Particle(), no shake).
- Enemy death burst at ~1075 â†’ effects.burst(24) (was 25 raw Particle()).
- Bullet render at ~1886-1896 â†’ camera.draw_bullets(with_glow=True).
- Objective panel at ~2399-2404 â†’ ui_hud.draw_objective_panel() (and removed "OBJECTIVE:" prefix from text variables).
- Pinned radio at ~2255-2275 â†’ ui_hud.draw_pinned_radio().
- Direct shake assignments at lines 498 (death seq, was =20) and 575 (breach bang, was =28) â†’ effects.shake(20) and effects.shake(28).

Ported call sites in mission2.py:
- _update_camera at ~3913-3976 â†’ delegates to camera.update_camera() with per-stage focus_factor or factor_fn (smoothstep for sniper stage, 0.38 for focus pulls, 0.14 default). Preserves mission2_camera_snap and mission2_camera_focus cutscene features.
- Local _burst() function at 782-788 â†’ replaced with _burst = effects.burst alias (24 existing call sites unchanged).
- Melee block at 3348-3362 â†’ player.resolve_melee() (also added STATE.melee_hit_done = True on hit, which M2 was setting inside the loop â€” now set after the resolver returns the hit enemy).
- Bullet/wall collision at 3529-3534 â†’ camera.collide_bullet_walls() + effects.play_impact() (was flat audio.play(); now 3D positional).
- Bullet/enemy hit at 3570-3571 â†’ effects.play_impact() (was flat).
- Bullet/player-hit shake at 3578 â†’ effects.shake(6) (was max() inline).
- Bullet render at 8273-8275 â†’ camera.draw_bullets(with_glow=True) (was missing glow halo).
- Objective panel at 7042-7047 â†’ ui_hud.draw_objective_panel().
- _draw_radio_text at 7413-7426 â†’ ui_hud.draw_pinned_radio().
- Player death shake at 3987 â†’ effects.shake(22) (was direct assignment).
- Tanker blast shake at 2699 â†’ effects.shake(160) (was direct assignment).

Verification:
- All 8 modified files pass py_compile (effects, camera, player, ui_hud, state, mission, mission2, weapons).
- All imports succeed: config, state, effects, camera, player, ui_hud, weapons, mission, mission2.
- smoke_test.py: 17 of 18 checks pass. The single FAIL is draw_settings (pre-existing bug â€” smoke_test passes 7 args to a function that requires 20; unrelated to this refactor).
- Integration tests pass:
  - effects.shake max-clamps correctly (5 then 3 â†’ still 5; 10 â†’ 10).
  - effects.burst spawns the requested particle count.
  - camera.update_camera snaps on first frame, lerps on subsequent frames, clamps to map bounds.
  - camera.collide_bullet_walls catches a 4px-thin wall at 24 px/frame bullet speed (M1's old AABB would have missed it).
  - player.resolve_melee correctly hits the enemy in cone+LOS and ignores enemies behind the player or behind walls.
  - ui_hud.draw_objective_panel and draw_pinned_radio render without error.
  - camera.draw_bullets renders without error.
  - Full M1 start_mission + game_update cycle works: player spawns at (224,160), camera clamps to (0,0) on first frame (player near top-left of map), camera follows when player moves to center.
  - M2 start_mission2 + game_update cycle works.
  - M1 restart properly resets STATE.camera_initialized to False.

Stage Summary:
- 9 shared helpers added across 4 files (effects.py, camera.py [new], player.py, ui_hud.py).
- mission.py: ~120 lines of inline mechanics code replaced with helper calls. 4 direct shake assignments converted to effects.shake(). 1 missing melee_hit_done reset fixed. 1 missing player-death shake added.
- mission2.py: ~80 lines of inline mechanics code replaced with helper calls. Local _burst() removed (alias to effects.burst). 2 direct shake assignments converted to effects.shake(). 1 missing bullet-glow halo added. 3 flat audio calls converted to 3D positional audio. 1 minimap-default bug fixed.
- state.py: 1 new flag (camera_initialized).
- All 5 of the top-priority inconsistencies from the prior mechanics-diff report are resolved:
  1. Camera recoil kick now applied in both missions (was dropped in M1).
  2. Bullet collision is swept clipline in both missions (was point-sample AABB in M1).
  3. Melee rules are unified (was 6 divergences between M1 and M2).
  4. Audio is 3D positional in both missions (was flat in M2).
  5. Screen shake triggers all use effects.shake() max-clamp (was direct assignment in M1).
- Plus 5 additional fixes: minimap default, bullet glow halo, camera first-frame snap, camera map-bounds clamp, objective panel + pinned radio layout unification.
- Produced artifacts:
  - /home/z/my-project/download/acaristan/effects.py (extended)
  - /home/z/my-project/download/acaristan/camera.py (new)
  - /home/z/my-project/download/acaristan/player.py (extended)
  - /home/z/my-project/download/acaristan/ui_hud.py (extended)
  - /home/z/my-project/download/acaristan/state.py (1 flag added)
  - /home/z/my-project/download/acaristan/mission.py (ported)
  - /home/z/my-project/download/acaristan/mission2.py (ported)

---
Task ID: modularize-1
Agent: main (Muse Spark)
Task: Modularize the project into src/tools/docs/assets/archive folders,
delete dead code, and split the 5 monster files via re-export shims.

Work Log:
- Branch chore/modularize. Redacted hardcoded apiKey in kilo.json
  (old key is still in git history â€” rotate provider-side + purge).
  Left .kilo/worktrees/accidental-platinum untouched (git worktree).
- Deleted dead code: m3_struggle.py (0 bytes), game_renderer.py,
  game_draw_unified.py, render_pipeline.py (unwired experiment) +
  __pycache__/mission2_recovered.py. Zero live importers; only
  comment references remained (cleaned in art_cache/acaristan/mission3).
- .gitignore: python/pycache/venv/build/dist + PDFs/TXTs/raw dumps +
  local save_data.json/settings.json + cb-shot dupes + archive/.
  git rm --cached the bloat; deleted build/, __pycache__, .ruff_cache,
  temp_out.txt, "uv - Copy.lock" from disk. dist/*.exe kept on disk,
  untracked. Root .gitignore was 1 line (.env).
- Archive: moved PDFs/, TXTs/, cbimg/, _cb_shots/, _cbpng/,
  game_source.pdf, build_code_pdf.txt, sdlaudio.raw to archive/
  (untracked). Nothing in the game loads the cb PNGs or menu-adjacent
  dumps. menu_theme.mp3 stays at root (MENU_MUSIC_FILE is root-relative;
  moving it would silently break menu music).
- src/ move (flat package, zero import rewrites): all game .py to src/,
  root acaristan.py is now a thin launcher (sys.path.insert src/ +
  import app; src/app.py = former acaristan.py with module-level loop).
  tools/smoke_test.py + tools/build_code_pdf.py (+setup_env.ps1,
  .build_settings.json), docs/*.md + manifest.json, scripts/ removed.
  build.bat gains --paths=src. README.md rewritten for the layout.
- app.py: `menu._dm_input` rebinding moved to `menu_mp._dm_input`
  (shim snapshots would shadow the MP browser's DM state).
- Splits (scripted section moves + re-export shims, namespace-verified
  missing:NONE/extra:NONE vs pre-split, smoke + headless exercises green):
  - mission.py (2556) -> m1_map/main/hotwire/update/draw. Fixed the
    _last_keys cross-part read via m1_update attribute access.
  - menu.py (5070) -> menu_widgets/main/mp/system. Moved _lerp_dt to
    widgets (was a widgets->main cycle); main reads SYSTEM's _footer_font
    (file redefines it); caught the tuple-assign blind spot
    (_pause_panel_h/w) in the splitter.
  - cutscenes.py (6288) -> cs_cast/route12/m3cell/chair/m3ops/engine.
    Moved _draw_vertical_gradient/_draw_light_cone to route12 to break
    the route12<->engine cycle. Zero byte-diff on all functions.
  - mission2.py (12176) -> m2_meta/world/starts/sniper/update/draw.
    Shared mutable globals (_last_keys/_objective/_radio_marks, owned by
    m2_world) routed via owner-attribute access; 5 lazy function-level
    imports break the world<->sniper<->draw<->update cycles.
  - mission3.py (14342) -> m3_meta/maps/world/flow/interrog/systems/draw.
    Moved tile consts (_DOOR/_MONITOR/_CELL) to meta, choice helpers to
    interrog, comms-relay logic to systems, _post_type_hold_frames to
    interrog. Module run-state routed via owner attributes
    (m3_maps: map/keys/objective/radio; m3_flow: dialogue/monitor/volkov
    state). 6 lazy imports total.
- Hardening from verification failures (all caught by checks, all fixed):
  - resolve_check (custom AST unresolved-name checker, full-module scope
    model) caught 6 missed cross-part refs (e.g. _dialogue_beats in
    interrog, _build_archives_world in systems).
  - Shim snapshot staleness: mission3._objective read via shim went stale
    after owner rebind (chair-break smoke check caught it). All 5 shims
    now `del` rebound names + PEP 562 __getattr__ live-view delegating to
    owner parts (reverse part order). Proven by livetest.py.
  - PUSH_NULL bytecode deltas (3.13 CALL protocol) on textually identical
    moved functions: proven benign via pixel-identical draw_menu render.
- Verification: baseline SMOKE TEST: OK (pre-change, stashed tree);
  final SMOKE TEST: OK; headless M2 (start+120 frames+draws) OK;
  headless M3 (start+60, breakout checkpoint+120) OK; compileall clean;
  per-function normalized source diffs identical except intended edits.
- Leftovers / follow-ups: kilo.json key rotation + history purge;
  dist/ rebuild to confirm build.bat --paths=src; menu_theme.mp3 could
  move under assets/ with a path update; deeper core/engine/ui
  sub-packaging (currently flat src/ by design); shims are permanent
  API surface (external code must not rebind state via shims â€”
  write through owner modules).


---
Task ID: m3-slice-5a
Agent: Qwen
Task: Mission 3 Phase 5 "The Kill Order" â€” sub-slice 5a (map & wiring, walkable, no combat) per docs/MISSION3_KILL_ORDER.md.

Work Log:
- Enumerated existing scaffolding first (plan Â§0 discipline): STAGE_KILL_ORDER constant, console set_stage jump, _start_kill_order_phase() stub, Archives north stairwell + locked m3_kill_order_exit door, draw/flow treating KO as Archives, Volkov ally + alarm systems, checkpoint-loader pattern.
- maps.py: _generate_kill_order_map() (40x40): NW stairwell tower, west/east service corridors, central lobby with 5 pillar cover pockets + SE mezzanine (5c marksman nest), 2 lobby closets (pickups + breacher shortcut doors), 3 south insertion corridors (5b sweep routes), loading dock with exfil van tile. Corridors >=3 tiles per plan Â§2.
- world.py: _KO_* tile constants (exfil, insert tiles, mezz, breach doors, pickups), _exfil_pos(), _build_kill_order_world() mirroring the Archives builder (loadout-preserving world swap, Door flags m3_ko_breach/locked, Volkov re-anchor, camera reset).
- interrog.py: stub replaced by real _start_kill_order_phase(force=False): world build, stage/phase flags, sweep/Volkov-window state seeds, alarm start, hp top-up, objective + VASILE kill-order radio beat, scheduled Balaceanu PA beat.
- flow.py: _update_kill_order_stage() (PA beat, 4-rung objective ladder, dock commit rule), _ko_zone_of() zone graph for 5b, start_mission3_kill_order_checkpoint() with full archives-mirror loadout (interrogation left player disarmed â€” first pass missed it, HUD showed RESTRAINED; fixed), KO branch in _update_stage builds world on dev-console stage set.
- systems.py: Volkov ally follow gate extended to STAGE_KILL_ORDER.
- draw.py: _game_draw_kill_order() (Archives entity pipeline mirror: corpses/enemies/overlays/particles/decals/pickups/Volkov/HUD/death overlays) + _draw_ko_dressing (stairwell steps, mezzanine nosing, dock crane/van/crates, pulsing exfil marker), _draw_ko_nav_arrow, _draw_ko_system_prompts (SEALED breach-door tags, exfil notice); dispatch split Archives/KO. Alarm strobe windowed (1.2s flash per 4s) â€” the lockdown effect's continuous cycle was unreadable as a phase-long state.
- game_core.py: start_mission3_kill_order_checkpoint delegate; m3/__init__.py exports.
- tools/smoke_test.py: check_mission3_kill_order_walk (stage/world/alarm/4-sealed-doors/90 updates+draw).

Bugs found & fixed during verification:
- Map gen ordering: west corridor wall_rect overwrote the stairwell doorway D-tiles (flood-fill caught it: spawn sealed in tower). Doorway now placed after both rings exist.
- systems.py missed STAGE_KILL_ORDER import (NameError in smoke); draw.py missed _exfil_pos import.
- Checkpoint loadout: player_disarmed not cleared + k9 ammo fields missing (HUD RESTRAINED); mirrored archives checkpoint block.
- Alarm strobe continuous red made the phase unreadable; windowed it.

Verification: flood-fill connectivity (all 12 zone targets reachable, breach doors sealed); archives->KO vostral-gated handoff; 17-waypoint headless walk with real game_update/game_draw (objective ladder cycles all 4 rungs, commit flag flips at van); Volkov follow-A* re-anchors and tracks on new map; SMOKE TEST OK incl. new KO check; visual stills rendered (ko_map_preview.png).


---
Task ID: m3-slice-5bcd
Agent: Qwen
Task: Mission 3 Phase 5 "The Kill Order" â€” sub-slices 5b (sweep director), 5c (overwatch pin + Volkov window), 5d (dock holdout + exfil) in one run, per docs/MISSION3_KILL_ORDER.md.

Work Log:
- New module missions/m3/sweep.py (~450 lines) owns all Phase-5 combat runtime; flow.py stays a thin ladder (one update_kill_order() call per tick), systems.py gets a 6-line coordination hook, draw.py gets laser + dressing hooks.
- 5b director: 5-wave schedule (20 bodies: 2 shield / 4 breacher / 2 marksman / 3 technician / 9 guard) all via _spawn_m3_guard(enemy_type=...) so role stats + gear + gear-corpses apply; whole-wave concurrent cap <=9 (withholds if current+incoming > cap); fireteam coordination via systems._m3_choose_enemy_target hook (leader A* to last-seen, members hold role offsets: shield point leads, breachers wide flank, techs trail); last-seen from CHASE states + player muzzle-flash edge; 20s sweep-line zone advance; 45s anti-turtle breacher charge on nearest closet door (rubble-open + shake(18) + debris bursts + breach/rattle audio + floating tag); stairwell set-piece charge under the player as wave 0 lands.
- 5c overwatch: mezzanine marksman nest; two lobby pin lanes; exposure = in-lane AND not covered (barrier/wall proximity test); 54-frame (0.9s) red laser telegraph (draw_overwatch_laser) then 2-round burst (enemy bullets, sniper_crack + positional concrete_impact, bracket burst, shake(5)); cover or nest assault resets telegraph; nest kill drops mag+bandage loot + VASILE line. Volkov window: 5:00 ticks in-stage, radio thresholds 3:30/2:00/0:45, bail at 0 = walk-off up the stairwell (180f, systems._update_volkov_ally branch) then despawn; Maru ghost-channel fallback; commit at van freezes window.
- 5d holdout: commit starts 45s garage-door cycle (shutter render in KO dressing); T+20s breach charge on dock side door; wave 4 inserts; door open + player at van -> _stop_m3_alarm + STAGE_BROADCAST + request_broadcast_cutscene + branch-specific exfil radio (VASILE van / MARU roof cage); bailed branch swaps van for roof-line cage dressing.
- Radio script per plan section 6 implemented with mark-once events; Balaceanu PA beat from 5a retained.

Bugs found & fixed during verification (battery caught all):
- Concurrent cap overshot (wave size not counted in the gate) -> whole-wave withhold check.
- Window "arming" line re-armed every tick, undoing the holdout deactivation -> one-shot arm + deactivate on bail.
- Director state (STATE.m3_sweep) survived STATE.reset() across checkpoints -> reseed in _start_kill_order_phase.
- Test-side errors (triple-quote delimiter ate an assert string; wrong event key; wrong measurement windows) fixed in tests, not game code.

Verification: smoke test OK incl. extended KO check (wave-0 insertion asserted); headless E2E batteries: waves 0-3 flow under attrition with cap held (max 6 live), wipeout reaches wave 4 pre-commit, anti-turtle breach 4->2 locked doors during lobby dwell, overwatch fires exposed / silent in cover / resets on nest assault + loot drop, window thresholds + bail walk-off + despawn, commit freeze, holdout side-door breach + cycle, exfil to broadcast on BOTH branches (Volkov / bailed), update-only perf delta +7.1 ms/f headless for +9 enemies +10 corpses (leader-only pathfinding keeps A* bounded). Visuals: ko_action_preview.png (laser pin, holdout shutter alarm-off/on, breach sealed->charge->blown).


---
Task ID: m3-ko-playability-audit
Agent: Qwen
Task: Answer "is the Kill Order map REALLY 100% playable?" with a repeatable headless audit + fix everything it finds; re-cut the preview video with a combat-competent bot.

Tool added: src/tools/ko_playability_audit.py â€” 7 checks: tile flood-reachability, enemy A* inserts-x-zones, WALK-ONLY full completion (A*-routed key-state bot, real door auto-open, real 45s door cycle, exfil to broadcast), Volkov bail walk-off, pin-lane/cover sanity, closet-loot accessibility, grand-tour soft-lock sweep (jitter budget).

Real bugs found & fixed:
- maps.py: lobby->south junctions were DOUBLE walls (lobby bottom ring row 27 + south top ring row 28); doorway_h only opened row 27 so three doors opened into solid rock. Punch second layer; 2x2 collapse pass turns them into clean 2-wide openings. (Flood check had missed it: two narrow side pairs kept the map connected.)
- sweep.py: closet loot was unreachable unless the player turtled 45s; wave-3 tech flush now breach-charges both closet doors open mid-phase.
- config.py DOOR_OPEN_RANGE 48 -> 56: 48 exactly equalled the collision stand-off distance, so any player approaching a door with >=1px sideways offset (dist 48.17 > 48) could NEVER trigger auto-open â€” a game-wide latent soft-lock, not just KO. Other missions only avoided it because corridors align approaches.
Audit-side fixes (test bugs, not game bugs): A*-router instead of hand waypoints, straight-through door-node smoothing (waypoint ON a door tile = diagonal corner jam outside open range), 2-wide doorway pair logic, bail tested away from the van (commit deactivates window by design).

Result: AUDIT ALL PASS 7/7 â€” walk-only completion 3644 ticks with every critical doorway opening under the player; grand tour of all zones 4323 ticks, 0 unstuck events; both exfil branches re-verified; smoke OK.

Video v2 (ko_phase5_preview.mp4): v1 bot "did nothing" because headless mouse-aim never reaches STATE.player.angle (get_scaled_mouse inert offscreen) â€” every shot flew at a stale angle. v2 sets the angle directly with target-leading, burst-fires through weapons.handle_shoot(), strafes, seeks pillar cover when the overwatch laser paints it, and assaults the nest (radio confirms "Nest is dark"). Renders real gameplay 60 ticks/s -> 30fps MP4.


---
Task ID: m3-ko-dev-commands
Agent: Qwen
Task: Dev-entry surface for Slice 5 â€” audit what existed, close the gaps.

Found: console set_stage kill_order existed but was SILENTLY BROKEN (_start_kill_order_phase's re-entry guard keyed off mission3_stage, which the console pre-sets -> build skipped); no CLI boot flag existed while every other slice has one.
Added: app.py flag block --dev-mission3-kill-order (+ --m3-kill-order / --m3-part5 / --dev-m3-part5 / --m3-phase5) mirroring the archives checkpoint pattern; guard re-keyed to world state (m3_ko_world_built AND MISSION3_MAP identity, since the flag survives STATE.reset across mission instances).
Verified: flag boots headless into the loop (exit 124, no traceback); console set_stage path builds world + trips alarm + spawns at stairwell; checkpoint-after-console and double-checkpoint sequences OK; audit 7/7 and smoke OK after the guard change.
Docs: MISSION3_KILL_ORDER.md gained a "Dev entry points" section.


---
Task ID: m3-ko-volkov-visibility + zorder/los fixes
Agent: Qwen
Task: Three play-feel bug reports: blood over corpses, overwatch through walls, invisible Volkov.

- m3 draw passes (4): blood-decal loops ran AFTER corpse draws -> pools rendered on top of bodies. Moved under corpses (m1/m2 already correct). Verified by rendered still.
- sweep overwatch: no LOS gate -> laser/rounds ignored walls. Added _wall_blocks_line gate; discovered nest room-center origin makes every sightline cross his own ring walls, so introduced a firing aperture at the mezzanine doorway (aim tile on the lobby side, since an origin inside the closed door's collision rect self-blocks). Laser/muzzle/LOS all originate at the door mouth now. Verified: telegraph 0 behind pillar, fires in open lane. M2 sniper audited: already LOS-gated, untouched.
- Volkov: update gate included STAGE_KILL_ORDER but _draw_volkov_ally's stage gate did not -> ally simulated but invisible in Slice 5. Gate extended; verified on/off/on pixel check (78/0/78 tag-color pixels) plus visual crop (name tag, coat, cig, support tracer).
Regression: smoke OK, playability audit 7/7.


---
Task ID: m3-ko-sniper-cutscene-difficulty
Agent: Qwen
Task: Three reports: marksman pin reads as shooting without seeing; Archives->KO handoff has no cutscene (every other phase change does); sweep enemies are sitting ducks.

- Honest pin: the marksman now physically steps up to the mezzanine doorway while engaged (direct pin-stepping in _update_overwatch â€” Enemy.update recomputes its own vision against handed coords, so target-coords can't walk him) and withdraws into the room when you break lane/cover. Laser, muzzle and LOS all originate from his actual body. Verified: 4px from aperture engaged, 4px from nest withdrawn.
- KO intro cutscene: STAGE_KO_TRANSITION holding stage + request_ko_transition_cutscene flag + gc.ko_transition_shots (3 in-engine shots: stairwell breach-charge pop, aperture laser sweep + PA strobe, dock van/Volkov reveal) rendered by m3.draw_ko_transition_cinematic on the LIVE KO map (directed camera, restored positions); app.py consumes the flag like the Archives transition; archives exit now prebuilds + holds; checkpoint/console entry still skip straight in.
- Difficulty/pressure pass: ROLE_TUNING (shield 260hp / breacher 160 / marksman 120 / guard 110 / tech 100, tightened cooldowns, raised damage) applied at insertion; waves trickle in on 24-tick cadence instead of teleport-crowds; spawn tiles moved to cover/off-sightline positions (corridor bends, behind doors, dock edges); entries seeded with your last-seen so they hunt on arrival; sweep-line advance 20s->15s, anti-turtle 45s->35s, wave cadence tightened. Shield frontal block (existing shield_angle_width) now matters at 260hp.
- Audit inserts now derived from sweep._WAVES (120 insert-x-zone pairs).
Regression: smoke OK, audit 7/7, cutscene handoff + direct-entry + cinematic render + tuned stats all verified headless.


---
Task ID: m3-ko-holdout-mags-cutscene-flag
Agent: Qwen
Task: Three reports: dock holdout had no pressure (stand 45s, nothing happens); Volkov stopped tossing mags in Phase 5; dev flag skipped the new intro cutscene.

- Holdout assault stream: _HOLDOUT_STREAM rotates a fresh pair every 150 ticks from four gates (south1/south2/south3/dock-side-interior once breached, east corridor) until exfil, cap-respecting. Verified: 11 distinct enemies pour in during the door cycle (was 4 total), ~3k near-player samples.
- Volkov mag resupply wired into _update_kill_order_stage (was Comms/Archives branches only); suppressed after bail. Verified: dry K-9 in KO -> mag throw within 300 ticks.
- --dev-mission3-kill-order (and aliases) now sets request_ko_transition_cutscene so the dev flag plays the phase-intro cutscene like the campaign handoff; checkpoint/code paths that need silence clear the flag.
- Crash guard: _spawn_sweep_member uids bookkeeping tolerates idx beyond st["waves"] (audit swaps _WAVES=[] for traversal runs; holdout stream uses team idx 4).
Regression: smoke OK, audit 7/7 (walk-only completion now runs WITH holdout pressure â€” hp-restored bot still exfils), dev-flag boot clean.

---
Task ID: m3-ko-transition-cutscene-directing-pass
Agent: Qwen
Task: Report: the Slice 5 (Kill Order) transition cutscene is unreadable â€” murk voids, actors off-frame or prone-looking, invisible FX.

- Root causes: draw_ko_transition_cinematic stacked its own vignette(150)+scanlines ON TOP of the app-level vignette(180)+scanlines (every other cutscene scene relies on the app pass only); aperture shot focused the camera 7 tiles away from its actors (both off-screen for the full 2s); van shot was fully static; breach pop fired exactly on top of the player; alarm strobe tint was alpha 26 (invisible under post); laser was a 1px hair; player/Volkov facing was never directed (top-down sprites read as prone bodies); motion durs (1500/1800) froze before shot min_ms (1600/2000).
- Directing pass (single function, m3/draw.py): per-shot authored facing + restored afterwards; camera frames the naming geometry AND both actors (stair steps -> door handoff; mid-lobby pillar cover with mezzanine doorway above the caption box; dock push-in on the van); breach charge pops the door AHEAD of the descent so the pair walks through the smoke (pays off Volkov's line) with spark burst, scorch and rising wisps; self-timed windowed alarm strobe at readable alpha; marksman laser = halo+core beam out of the doorway that searches the lobby and ends painting the actors' cover; cold PA flicker for Balaceanu; warm work-light pool over the exfil van; durs synced to min_ms; internal vignette/scanlines removed.
- Robustness: helpers that paint onto the module-global `screen` (_draw_ko_dressing/_draw_m3_doors) now get it swapped to the shot target for the duration, so the cinematic renders identically in-game and headless (the old _cut_frames/ko_* probes saved a different surface than the global and misleadingly showed no dressing/van; those stale frames deleted).
- New tool: tools/probe_ko_cutscene.py â€” headless frame probe mirroring app.py CutsceneRenderer (scene -> vignette/scanlines/letterbox -> caption); before/after strips in _cut_frames/ (cur_* vs fix_*, ko_transition_before_after.png).
Regression: compileall clean, smoke OK, state-leak check PASS (player pos/angle + Volkov pose restored after every shot), 36 probe frames eyeballed across all three shots.

---
Task ID: m3-ko-cutscene-illustrated-rehaul
Agent: Qwen
Task: Owner verdict after the directing pass: still horrible â€” rehaul the whole cutscene together.

- Root cause of "still horrible": the KO transition was the only cutscene in the game rendered as a top-down view of the live tilemap ("gameplay with captions"). The chair-break rehaul had already established why that fails and what the house style is instead: dark vector compositions, motivated lighting, side-view cast sprites, location tags (chair.py: _cb_cinematic_bg docstring).
- Full rehaul into the house style, new part module cutscenes/m3ko.py (pure functions of t, zero STATE reads/writes):
  * stairwell â€” side-section stair tower, pair descends under the lockdown strobe, breach charge pops the door ahead of them, smoke + warm crack light, handheld shake on the pop;
  * aperture â€” lobby low angle: backlit mezzanine doorway with marksman silhouette, volumetric laser with dust glints searches the floor and snaps onto the pair's pillar edge (spark + flinch), cold PA flicker, Volkov's hand on Biribel's shoulder;
  * van â€” dock reveal: shutter slit-light behind the van, open rear doors spill a warm pool, Volkov beckons, Biribel walks in with the Vostral dossier in hand.
  All three carry location tags like the Archives handoff shots; dust motes + micro handheld throughout; app-level vignette/scanlines/letterbox/caption left untouched (single post pass, house rule).
- Wiring: ko_transition_shots now point at m3_ko_stairwell/_aperture/_van with pacing min_ms 2600/2400/2600; engine dispatch updated; facade lists m3ko between m3ops and engine; the replaced top-down draw_ko_transition_cinematic deleted from missions/m3/draw.py (no other refs).
- Probe timings extended to cover the new beats (pop 900ms, laser snap 1950ms, walk-in 2000ms); before/after strip rebuilt (cur_* = top-down rev, rev_* = illustrated).
Regression: compileall clean, smoke OK, probe 18 frames eyeballed per beat; no STATE mutation possible by construction.

---
Task ID: m3-ko-cutscene-feel-pass-v2
Agent: Qwen
Task: Owner verdict on the illustrated rehaul: looks good but still... eh.

- Diagnosis: compositions were fine, the FILM wasn't moving. (1) Shots are input-paced (held until the player advances) so one-shot motion settled into dead tableaus; (2) cast glided with no walk cycle; (3) camera was a tripod with a tremor; (4) no insert shots, so the edit had no rhythm; (5) highlights didn't bloom; (6) SFX bed unused beyond the phase alarm loop.
- v2 feel pass (cutscenes/m3ko.py rewritten):
  * ALIVE-FOREVER rule: looping smoke plumes (recycling wisps), strobe cycles, laser micro-jitter + periodic spark ticks after the snap, shutter-slit shimmer, pool shimmer, breathing idle, Volkov keeps beckoning (impatient) â€” held frames verified alive at t=4200ms (rev_hold_*.png).
  * Camera: per-shot push-in (crop+smoothscale around a drifting focus), handheld micro-shake, cut-on-flash from the new insert into the stairwell wide.
  * Acting: _ko_actor wraps cast sprites with walk tilt + step bob while moving, breathing bob when held.
  * New insert shot m3_ko_charge (hide_caption, 1300ms): breach-pack close-up with hazard band, arming LED (blink rate ramps), wire run; breach flash + sparks at 1150ms, cut on the flash. Shot list now 4 shots (insert + 3 wides); stairwell wide opens post-pop with smoke already pouring (min_ms 2200).
  * Sound: KO_CUT_CUES in app.py fired once per shot from CutscenePlayer.update (door_rattle + breach on the insert, concrete_impact under the wide, elec_hum + bullet_snap on the laser snap, door_creak at the van); fired_cues set on the player so cues never double-fire.
  * Highlight glow via new _ko_glow (normal-blend get_glow + .copy()): _draw_bloom_circle is additive and stacks ~2.85x alpha at centre â€” it blew every highlight into a white disc; get_glow's cache is shared game-wide so the copy() also prevents set_alpha leaking into other systems.
Regression: compileall clean, smoke OK, probe frames per beat + held frames at 4200ms eyeballed; still zero STATE reads/writes in the cinematic.

---
Task ID: m3-ko-dialogue-consistency-pass
Agent: Qwen
Task: Owner verdict: the KO dialogue/radio lines make absolutely 0 sense; cutscene still has issues.

- Dialogue ground-truth audit against docs/MISSION3_PLOT.md + MISSION3_KILL_ORDER.md found: (1) dev-note leaks in player-facing strings â€” objective "(Holdout: Slice 5d)", objective "(Phase 6 â€” pending)", floating text + in-world tag "EXFIL POINT â€” HOLDOUT INCOMING (5d)", floating text "EXFIL â€” PHASE 6"; (2) Vasile's phase-init radio said the hunting teams are "yours now" and that HE was moving the van (the van is Volkov's; Vasile is remote comms); (3) the exfil van-branch bark "File's aboard. Drive. DRIVE!" was attributed to Vasile although Volkov drives his own van; (4) the lobby first-contact bark reused the cutscene's "Through that smoke" line verbatim at a moment with no smoke and no shield in sight; (5) the scheduled post-cutscene PA beat repeated the cutscene's aperture PA line almost word-for-word, so the player heard the same announcement twice from two systems.
- Rewrites (speakers/owners/timeline now consistent): cutscene stairwell = Volkov owning the van + bail tension ("My van's still staged at the dock â€” I haven't bailed on you yet..."); aperture PA tied to the on-screen lobby levels; van shot = VASILE remote intel over an empty-dock preview. Gameplay: init radio fixed (teams hunt you, Volkov's van, Vasile on comms); PA beat is now a distinct status-report announcement; lobby bark is a real contact call ("shield point ahead, go around his sight cone"); exfil van-branch bark moved to Volkov; all dev-note leaks stripped.
- Cutscene continuity: the van shot no longer shows Volkov (and Biribel) physically at the dock mid-intro â€” it is now an empty establishing preview with a time-based drift pan and a swaying crane hook, so nobody is in two places at once when gameplay resumes with Volkov on your six.
- Edit rhythm: charge insert now hard-cuts on the breach flash (shot flag hard_cut; CutscenePlayer skips the fade for it) instead of dissolving the punch cut through black.
- Location tags raised above two-line captions.
Regression: compileall clean, smoke OK, probe frames re-eyeballed (van preview composition holds without actors).

---
Task ID: m3-ko-cutscene-logic-bug-pass
Agent: Qwen
Task: Owner verdict: "there are bugs, like logical bugs" (cutscene + KO wiring).

- L1 campaign silence: the prebuild (seamless handoff) path returned before _start_m3_alarm(), so the lockdown siren played under the cutscene on the checkpoint path but NOT in campaign. Alarm now trips in the prebuild branch (idempotent; checkpoint path unchanged).
- L2 phantom breach: phase init replayed audio.play("breach") AFTER the cutscene, i.e. a bang with nothing on screen (the breach now lives inside the charge insert). Removed; radio_static kept for the init transmission.
- L3 stale radio under cutscene: on the checkpoint/dev-flag path init runs BEFORE the cutscene, so Vasile's init transmission typed over the cutscene captions and lingered after. New core.interactions.clear_radio_queue() (drops queue + silences live) called the moment the KO cutscene starts.
- L4 triple exposition: init radio restated stairwell/van info the cutscene now delivers; trimmed to what it uniquely knows (kill order signed, teams hunting, comms overwatch).
- Continuity/logic in the shots: van shot is an empty-dock preview (nobody in two places at once); charge insert hard-cuts on the flash; location tags clear of two-line captions.
- Stale tooling: root TEMP probe_cut.py crashed against the current sweep API (_formation_point/_floor_ok removed in the 5b refactor). Superseded by tools/probe_ko_behavior.py: same fairness/holdout/poison coverage, wall-grind section replaced by a live solid-tile check (0/3184 members in walls), stale expectation comments corrected (early insertion spawns are fair when far away: 0 dmg standing, none above row 9; 2/5 movers at 10s is by design â€” the line advances at 15s without contact).
Regression: compileall clean, smoke OK, behavior probe 5/5 sections run clean, KO cutscene probe frames re-eyeballed. Zip rebuilt.

---
Task ID: prop-placement-and-art-pass
Agent: Qwen
Task: Owner verdict: "in the entire game there are props inside walls, ugly props overall, etc."

- Placement audit (new tools/prop_audit_overview.py stitches full-map overviews through the real draw path; tools/prop_placement_audit.py checks every enumerable prop footprint against solid tiles): M2 had two traffic cones authored on guardrail 'B' tiles (16,57)/(30,42) â€” moved to (17,57)/(31,42); M3 reused ONE background-dressing anchor list across all four tilemaps, so on comms/archives/killorder most props either sat in walls or were culled by the overlap validator (7-9 of 12 invisible per map). Dressing, pipe runs and vent plates are now per-map tables (_M3_DRESSING_PROPS/_M3_PIPE_RUNS/_M3_VENTS in m3/draw.py) hand-picked on open ground with a tile margin; the validator stays as the safety net. New runtime guard missions.m2.world._nudge_props_off_solid() (called from _sync_story_prop_collisions, the single choke point after every bulk prop spawn) spirals any trigger-spawned prop out of solid tiles deterministically. Audit now reports 0 BAD / 0 SKIP on all seven maps.
- Root cause of the "black puddle / sticker" look: pygame BLEND_ADD / BLEND_RGBA_ADD ignore the SOURCE alpha channel. Every additive blit of an alpha-falloff sprite (yard floodlight cones, lamp wash pools, relay/status glows, CRT red wash + halo, breach fire flash, ember halo, walking-sim rig glow) rendered as a hard bright shape, and every `draw.ellipse(screen, (0,0,0,a), ...)` contact shadow on an opaque surface baked as a SOLID black blob (75 call sites). Fixed: new render_util.soft_shadow() (SRCALPHA temp blit) replaced all alpha-shadow ellipses; new render_util.add_radial() builds premultiplied opaque radial pools for additive lamp washes; remaining additive glows premultiply intensity into RGB (yard cones now nested premultiplied wedges that fade toward the throw).
- Prop art pass, both tiers: core/props.py procedural painters rewritten (crate stack on a pallet with plank seams/braces/stencils, shaded drums with rims+hoops+rust, strapped cable coil with tail plug, tapered bucket with wringer + leaning mop, two-shelf service cart with load + casters, coupled/flanged pipes) and tools/make_art_pack.py generators upgraded to match, sprites regenerated (89 sprites).
- Mission furniture/props: M3 maintenance boilers are now shaded cylinders (dome caps, weld seams + rivets, gauge dials, valve wheels, manifold stubs) with layered soft steam; laundry washers got gradients/door glass/control strips, folding table got legs + gradient + edged linen piles, carts got slats + rim + linen; guard-room briefing table shadow softened; M2 story cones (two-facet + reflective collar + base plate), barrels (gradient + rim + hoops), puddles (irregular blob + sky glint + ripples), signs (graded plate), spark boxes (graded body + hazard label); M2 'B' barrier tiles render as jersey barriers (graded body, lit ridge, base skirt, seeded scuffs) instead of flat grey crates.
* tools/golden.py still FAILs archives/comms/cell at 39/28/31 of 1120 px against a 22 px (2%) budget, i.e. still the pre-existing stale-baseline drift documented in m3-exterior-ground-material (39/27/25) and earlier entries. Archives is unchanged at 39 and cell is not sealed, so the cell 25 -> 31 movement is the intended t_g_* recolor; comms 27 -> 28 likewise. The golden baseline is owned separately and was deliberately not regenerated here.

- Tooling kept: tools/prop_audit_overview.py, tools/prop_placement_audit.py, tools/prop_showcase.py, tools/m2_walk_shots.py; evidence + before/after sheets in prop_audit/ (cmp_props.png, cmp_maintenance.png, cmp_m2_shelter.png, cmp_m2_road.png).
Regression: compileall clean, smoke OK, placement audit 0 BAD / 0 SKIP across m1/m2/m3x4/walk, room sheets + overviews re-rendered and eyeballed.

---
Task ID: collision-map-integrity-audit
Agent: Qwen
Task: Owner request: big audit for collision/map checks â€” maps correct, no extra/missing parts, no invisible collision.

- New tools/collision_map_audit.py: per map (M1, M2, M3 x4, walk) checks grid shape (jagged rows), border enclosure, flood-fill reachability from player start (sealed pockets, doors leading nowhere), collision-vs-tilemap both directions (invisible collision rects on passable tiles; solid tiles without wall rects; extra rects buried in walls), gameplay points (player/enemy spawns, desks, clues, pickups) on solid or unreachable tiles, and prop/furniture rects sealing 1-tile passages or covering door tiles. Writes colour-coded overlays to prop_audit/collide_*.png. Also new tools/collision_overlay_shots.py (collision rects drawn over real frames) which is how the mis-anchors below were eyeballed.
- Real bugs found + fixed:
  * M2: civilian car rect (41,25) parked half-inside the control-building south wall row (drawn car embedded in wall + collision in wall) -> moved to the open parking row (41,26).
  * M3 cell: background-dressing COLLISION anchors in world.py were still the pre-art-pass list, i.e. invisible walls where nothing is drawn anymore (east crates at 24.5 vs drawn 26.5, south cart/barrels inside the laundry west wall and the maintenance floor, hall crates 2 tiles off) -> synced to _M3_DRESSING_PROPS["cell"]; washer-bank collision rect spanned only 4 of 5 machines -> width now covers the whole bank.
  * Walking sim: 'K' tiles (11,3)/(15,3) were handled by neither the collision build nor the renderer (authored container blocks missing in-game) -> converted to containers; 'T' on the east border was an unhandled passable border tile -> closed to 'C', leaving the 'V' van-trigger tile as the single authored border gate (whitelisted in the audit); sealed 1x2 pocket inside the west container block (4,5)-(4,6) -> opened a south alcove mirroring the east block.
  * M3 room frames: _draw_rect_room_frame drew its wall ring from authored rects regardless of the tilemap, so on many rooms (maintenance 43%, server cage 47%, laundry 70% of the border) ghost wall segments sat on passable floor â€” walls the player could walk through. Frame runs + door jambs are now clipped tile-by-tile to real solid tiles (_frame_solid/_h_run/_v_run), so drawn walls and collision always agree; the tilemap renderer already draws every real wall.
  * M3 systems: added the missing "K" entry to _TILE_BASE (legacy-tier fallback parity; flagged by m3_room_audit section 2).
- By-design cases documented, not "fixed": Comms/Archives/KO builders treat exterior 'g' as out-of-bounds solid (cell map exterior stays walkable) â€” the audit now uses per-map solid sets; cell cot/sink collision rects sit inside their wall column because the sprites are wall-mounted (reported as info-redundant only).
Regression: compileall clean, smoke OK, collision audit 2 info / 0 real findings across all seven maps, m3_room_audit 0 findings, room sheets + walk/m2 shots re-rendered and eyeballed. Zip rebuilt.

---
Task ID: m3-slice5-beat-gates
Agent: main (Muse Spark)
Task: Owner report: in Mission 3 Slice 5 (Kill Order) you can sprint stairwell -> van and miss most of the action. Fix: hard beat-gates (2 stages, breach-charge unlock).

- Diagnosis: a kill-gate already blocked early boarding (sweep holdout/boarding gates), but every forward door was unlocked, so a ~20s sprint reached an empty dock and parked on "HOLDOUT LOCKED" while waves 0-3 trickled down via the sweep line; beats 1-2 (stair ambush, lobby crossfire/mezzanine assault) were bypassed spatially, the Volkov 5:00 window froze at ~4:40, and the pre-commit nav arrow pointed straight at the van, routing rushers past the action.
- world.py: new _KO_BEAT_GATES (tile -> required cleared wave): lobby->south row-27 junctions (9,10 / 19,20 / 31,32) sealed until wave 0 clears; south->dock row-32 doors (6,7 / 19,20) sealed until wave 1 clears. _build_kill_order_world tags them (d.m3_ko_beat_gate) + locked. The (31,32) dock side door stays owned by the 5d holdout breach.
- interrog.py: _start_kill_order_phase re-seals beat gates on (re)start, since a checkpoint reload reuses the KO world and would otherwise inherit open gates.
- sweep.py: new _update_beat_gates (breach_door + Volkov/Maru radio per gate, one-shot via ko_beat_gate_* marks; requires wave cleared AND no members still queued) wired into update_kill_order; new _update_stuck anti-soft-lock (a gated-wave member with no real movement for ~10s re-inserts on a fresh bearing 3-5 tiles from the player; pinned nest marksman excluded; holdout stream excluded).
- flow.py: objective ladder now leads with gate states ("clear the ambush to open the south gates" / "drop the marksman to open the dock gates").
- draw.py: _draw_ko_nav_arrow pre-commit targets nearest sealed gate -> live sweep centroid -> van (was: van always); _draw_ko_system_prompts shows "SEALED - CLEAR SWEEP TEAMS (N LEFT)" on beat gates.
- src/tools/ko_playability_audit.py: now 9 checks. Grid split into BREACH_LOCKED/BEAT_LOCKED; checks 3/7 pre-open gates + route on the open grid; check 2 routes post-clear topology; new check 8 (8a-8f: gates sealed at start, sprint held at each gate while its wave lives, wipe -> breach+radio, full holdout -> 45s cycle -> broadcast) and check 9 (wedged member re-flanks onto a walkable tile). Also fixed the stale sys.path bootstrap (src/src) and the offscreen video driver (dummy, matching every other tool).
- Incidental fixes in src/tools/smoke_test.py (same stale sys.path bug -> ModuleNotFoundError; golden.py looked next to itself instead of root tools/). KO walk check passes.
- Pre-existing, not caused by this change: golden_images drift 25-33/1120px on archives/comms/cell (KO code never executes there; run-vs-run is 0px off; scattered full-frame pixels = stale baseline from an older tree state). Left for the baseline owner; root gate has no golden check and is green.
Regression: compileall clean; root tools/smoke_test.py SMOKE TEST: OK; src/tools/smoke_test.py all green except pre-existing golden drift; ko_playability_audit ALL PASS (14/14).
---
Task ID: m3-slice6-analog-clock
Agent: Cline
Task: Owner request: make the Mission 3 Slice 6 timer render as an analog clock instead of the digital plate.

- src/missions/m3/systems.py: _draw_broadcast_address_clock (the "STATE ADDRESS 22:00" plate under the minimap) re-drawn as an analog wall clock. In-game time is derived from STATE.m3_bcast_time_left (1 tick = 1 display-second, BCAST_TIME_LIMIT = 360s, so the dial opens at 21:54 and lands on 22:00): hour + minute hands, thin sweep hand (1 rev per in-game minute), 12/3/6/9 long ticks, red 12 o'clock deadline notch, and the old drain bar replaced by a remaining-time ring outside the face (full at spawn, drains to the notch). Digital "IN MM:SS" line kept centered under the dial for legibility; urgent last-minute blink (text + ring pulse) and the failed state (red border/ring, hands pinned at 22:00, ADDRESS COMPLETE) preserved. Guards unchanged: Broadcast stage only, hidden while the upload OS is open (the OS keeps its own CRT text readouts).
- Placement unchanged (right-aligned under the minimap, top-right fallback); added a bottom screen clamp now that the panel is taller (~147px vs 52px).
- Facade-safe: same name/signature, already exported by missions/m3/__init__.py; no new module state, no new imports (math/time/pygame/BCAST_TIME_LIMIT already available).
- Regression: compileall clean; root tools/smoke_test.py SMOKE TEST: OK (exit 0, incl. mission3_broadcast_draw); all four clock states (06:00 / 03:30 / 00:45 / failed) + minimap placement rendered offscreen and eyeballed; src/tools/smoke_test.py golden still the documented pre-existing drift (archives/comms/cell only - no broadcast scene in the baseline).
---
Task ID: m3-exterior-ground-material
Agent: Cline
Task: Owner report: Mission 3's exterior dirt ground (the 'g' field) reads as a repeating quilted/patterned mud field. Fix: retune the tile material and add world-space ground dressing.

- tools/make_art_pack.py: 'g' palette retuned mud brown (40,36,32) -> dusty gravel (43,42,38), and the four tile variants rewritten as small low-contrast marks (speckle, pebbles, faint drag ticks) in place of the old motif set (big damp-patch ellipses + long vertical ruts) whose fixed phase inside every 64px tile was what read as a quilt once the base was tiled. Regenerated the pack and confirmed only the four t_g_*.png changed, i.e. the pass itself stays deterministic.
- src/missions/m3/systems.py: _TILE_BASE["g"] mirrored to the new palette (legacy-tier fallback parity). 'g' is Mission-3 exclusive, so no M2 collateral.
- src/missions/m3/draw.py: new world-space ground pass shared by all five M3 maps - called from the four _bake_m3_* bakes right after _render_cell_bg, from the ACA_STATIC=off fallbacks of the cell/archives/comms/broadcast paths, and from the Kill Order path:
  * _draw_m3_exterior_ground(cam_x, cam_y) does three things: soft tone blotches (one seeded slot per 5x5 tiles, the slot probing up to 4 tiles so the 3-4 tile wide exterior strips still get their share; 96/112/128px; ~55% dark damp, 45% light dust), a 16px contact-shadow band where open ground meets a wall, and sparse scuffs + dry weed sprigs on a 2x2-tile slot grid.
  * Everything is seeded by world position, never time, and drawn in world space - chunk bakes, goldens and replays stay identical. Blotches/AO are skipped unless a 3x3 tile block is real open ground (largest half-size 64px = exactly that block's one-tile reach), so dirt is never sprayed onto a facade or an interior floor; narrow exterior strips are why the block test is 3x3 and not 5x5.
  * Removed the old grid-locked per-tile seam loop from _draw_m3_background_dressing: it drew its seams on the tile lattice, which is what made the field read as tiles instead of ground.
- Drift/regression: compileall clean; tools/smoke_test.py SMOKE TEST: OK (exit 0); tools/golden.py unchanged in substance - re-rendering every scene with the new pass stubbed off moves 0/1120 signature samples, and the only failures stay the documented pre-existing archives/comms/cell drift (39/27/25 px off); bench static=on art=new 9.42 ms/frame (106 fps), ACA_STATIC=off 13.51 ms/frame (74 fps) with the pass itself 0.87 ms of that.
- Verified before/after at 17 cameras over cell/archives/comms/broadcast/ko (shots + 2-3x zooms, and the pass isolated on a white surface per map: 2-8 blotches and 35-54 AO bands per view): the repeating ellipse lattice, the 1px tile seams and the vertical ruts are gone; the field now reads as packed dirt with soft large-scale tone variation and a wall-base shadow, and multi-chunk screens composite without seams.

---
Task ID: m3-neutral-gravel-and-slice6-boundary
Agent: Cline
Task: Owner report (two items): (1) Mission 3's exterior ground reads as dirt-like brown, retune it to neutral gray packed gravel; (2) Slice 6 has a part that looks like you can go out of the playing area but is invisible.

* Root cause of (2) was a render/collision mismatch, not faulty movement collision. In Broadcast and Comms the tile art paints 'g' as open compound gravel, but both world builders add every 'g' tile to STATE.walls (world._build_broadcast_world / _build_comms_world both test `tile in ("C", "g")`). So any 'g' sharing an edge with floor read as a way out and the player then hit an invisible wall one tile later.
* src/missions/m3/maps.py: new _seal_exterior_shell(g) converts walkable-edge 'g' to wall 'C'. Collision-neutral by construction - both chars are solid in these two maps, so the walkable shape is byte-identical and only the art changes. Called from the Broadcast generator (final pass, after the 2x2 door collapse) and the Comms generator. Broadcast 18 tiles sealed, Comms 6; char-level delta 22 and 6 respectively.
* src/missions/m3/maps.py: removed two decorative Broadcast north hatches (green room and control room). Both opened onto a solid rock band, and the control room's west leaf was additionally walled off by the console divider, so both tripped the audit's "door leads nowhere" finding.
* Verified collision-neutrality on both maps by rebuilding the pre-change grid (seal stubbed off, hatches restored) and diffing against the shipped one: solid-tile sets identical (Broadcast 640 vs 640, Comms 1684 vs 1684), walkable sets identical, live STATE.walls rect-for-rect identical. The only non-neutral delta is the 4 hatch leaves (D -> C) that were deliberately removed, and the only tiles that lose reachability are those same 4; every objective tile (spawn, corridor, studio gate, studio floor, PC vault, green/control room, both stores, antechamber) stays reachable.
* tools/collision_map_audit.py: added the Broadcast scene and the solid-'g'-at-play-boundary check. Both maps now report zero boundary leaks (Broadcast 22 -> 0, Comms 6 -> 0) and the "door leads nowhere" finding is gone. Remaining 2 TOTAL FINDINGS are the pre-existing info-redundant wall-prop notes in m3_cell, a map this change does not touch.
* Art level proof over all 22 changed tiles: every one now resolves to wall art instead of ground art via artpack.wall("C", ...) vs artpack.tile("g", ...), 0 missing or mismatched surfaces and 0 pairs resolving to the same surface. (Full-frame A/B pixel diffs were not usable as evidence - the ticking mission clock and per-frame AI/particle state move thousands of pixels between two runs of the identical map, so I measured at the tile-art level instead.)
* tools/make_art_pack.py: 'g' retuned from the previous dusty-gravel/mud reading to neutral packed gray, base (46,46,48), brown cast and damp-patch motifs removed, world-space sprigs replaced with aggregate chips and blotches neutralized. Only t_g_0..3.png regenerated; a hash comparison confirmed no other art in the pack changed, so the pass stays deterministic. Sampled the shipped tiles: mean red-blue spread -2.0 (neutral) on all four variants, luma spread 6..18.
* Regression: compileall clean; tools/smoke_test.py SMOKE TEST: OK (exit 0, incl. mission3_broadcast_draw).
---
Task ID: m3-broadcast-timer-length
Agent: Cline
Task: Owner feedback: the 6-minute broadcast address countdown is too much.

- src/missions/m3/meta.py: BCAST_TIME_LIMIT 360*60 -> 180*60 (6 min -> 3 min). Single constant; flow.py (_start_broadcast_phase, _retry_broadcast_slice) only assigns it, and systems.py derives everything else from it, so there is no second place to keep in sync.
- Sized from measurement, not guesswork. Headless probe of the real slice (broadcast checkpoint, wave chain, walk to PC): with instant kills and perfect play the floor is 17s to the PC plus the upload OS's own 720 ticks (12s) = 29s absolute floor, against 12 enemies across 3 waves (3 corridor / 4 gate flankers / 5 booth). 180s leaves ~6x headroom over that floor, so real combat and deaths still fit, while the dead padding is gone.
- Safe to tighten because the wave scheduler is event-driven, not time-based: waves advance on entering the corridor, on enemies_alive == 0, on the gate unlocking and on PC proximity, never on a timer. Shortening the clock cannot strand a wave.
- Failure stays a soft loop, not a game over: _fail_broadcast_timeout plays broadcast_fail_shots and _retry_broadcast_slice rebuilds the wing with a fresh full timer.
- src/missions/m3/systems.py: updated the two stale "21:54" comments in _draw_broadcast_address_clock (the dial opens at 22:00 minus BCAST_TIME_LIMIT, now 21:57). The code already derived the opening time from the limit, so this is comment-only - no behaviour change.
- Note the upload OS (ui/upload_os.py) burns the same clock: its 1/720-per-tick progress and the 12s dwell run while _update_broadcast_stage keeps decrementing, and the plate is deliberately hidden while the OS is up. A 3-minute limit therefore really does charge the player for the upload.
- Verified: all 9 clock states render offscreen (3:00 / 2:30 / 1:30 / 61s / 60s / 59s / 30s / final tick / failed) and the urgent threshold flips at exactly left <= 60*60; the dial reads IN 03:00 with a full ring at spawn and goes orange with a partial ring at 1:00. compileall clean; tools/smoke_test.py SMOKE TEST: OK with all six broadcast checks green, including mission3_broadcast_timeout_retry and mission3_bcast_fail_shots_render. Floor probe re-run against the new limit: 29s floor vs 167s remaining at the PC.
---
Task ID: mp-announcement-trailer
Agent: Super Z
Task: Owner request: multiplayer announcement trailer built from REAL in-game footage (no staging), v2 fix for "teammate name/team not visible", and packaging of the updated project.

- trailers/mp_announce/ (new): mp_announcement_master.mp4 (46.2 s, 1920x1080@30, h264+aac 192k, -15.6 LUFS / -2.7 dBTP), host_flow.mp4 + client_flow.mp4 (real KRAPNET 2v2 TDM captures on foundry, room VOLK-2M00M-4K9H4Z; two rendered MatchScreen seats + two headless protocol bots over real loopback TCP, driven through the real input paths), chapters.json, host_flow.foley.json (70 events / 9 kills), combat_debug.json, report.json.
- tools/mp_trailer_capture.py (new): headless capture driver for the above. ArenaBot navigates A* on the tile grid with diagonal-preserving axis quantisation (threshold 0.35) and a wedge escape (stuck > 15 ticks -> 12-tick perpendicular slide); WINGMAN mode is the v2 fix - the client seat (MIRELA, host's IPA teammate) orbits the HOST at 70-150 px so both name tags stay on camera through the fight. The name-tag mechanic itself was already correct in src/ui/arena_view.py (_draw_name_tag draws name+team for every non-local player on camera); the v1 footage simply never had the teammate in frame, so no game-source change was needed.
- tools/mp_trailer_assemble.py (new): post-production assembler - cards rendered through the game's own renderer, chapter-relative EDL (re-flows automatically on re-capture), sim-tick -> capture-second foley mapping (GO chapter = sim tick 0, because match_screen._update_host early-returns during the countdown), menu_theme bed + diegetic foley stem + design events, loudness chain via alimiter(attack=5:release=90) then makeup + true-peak guard. Usage: python tools/mp_trailer_capture.py, then python tools/mp_trailer_assemble.py [--keep-stems].
- tools/mp_remaster.py, tools/debug_stem.py, tools/preflight_bot_test.py (new): audio-only remaster from a --keep-stems workdir, cProfile run of the foley stem, and an offline GridNav/ArenaBot/ArenaSim pre-flight (no sockets).
- All five tools use repo-relative paths (ROOT = Path(__file__).resolve().parents[1]) and write outputs into trailers/mp_announce/. No game-source files were modified by this work.

---
Task ID: m4-the-aftermath-build
Agent: Qoder
Task: Build Mission 4 "The Aftermath" end to end following the M3 package pattern, wire it into the campaign chain, and replace the mission4 ending stub with a real cutscene. Sliced W1-W6, each gated by `python tools/smoke_test.py` (SMOKE TEST: OK) + `python -m compileall -q src tools`.

- W1 (Slice 0) integration chain + playable shell: STATE gains the mission4_stage / m4_* flags + request_mission4_ending + tower checkpoint; save_system `_MISSION_RECORDS` gains MISSION4; game_core adds `_is_mission4_active()`, start_mission4()/start_mission4_tower_checkpoint() wrappers and routes MISSION4 FIRST in game_update/game_draw/handle_interact/debug_jump; app.py wires --dev-mission4, the ending-request routing, _CutsceneState._handle_end (after==MISSION4 / MISSION4_COMPLETE), _MissionCompleteState MISSION3->M4 chain, and _SlotSelectState._activate_slot (MISSION_3 -> start M4, MISSION_4 -> FULL CAMPAIGN COMPLETE, progress==m4 -> resume at checkpoint); dev_jumps gains m4 / m4-tower; hud MiniMap palette gains an m4 night-city entry. New m4 package (meta->maps->world->flow->systems->draw) as a PEP 562 re-export facade with _LIVE_STATE.
- W2 (Slice 1) STAGE_AFTERMATH curfew city: 40x40 procedural street map (ruined boulevard, checkpoints, safehouse->station), 3 named zones, rain/radio_static beds + timed gunshot_distant events, sparse guard/marksman IPA patrols (M4_ROLE_TUNING ported from m3.sweep values, not imported), Vasile radio story beats establishing the 48h chaos + Volkov's flight.
- W3 (Slice 2) station interior: 24x20 _generate_station_map() (south hall / north transmitter / east studio), friendly Maru+Vasile pose-draws, the KRAP-MAG liaison typewriter dialogue (M3 cadence ported) with a single tone choice, jammer install interact, and start_mission4_tower_checkpoint() as the STAGE_COMMIT resume point.
- W4 (Slice 3) STAGE_COMMIT siege: wave director in world.py (<=6 concurrent loyalist fireteams from 3 insertion doors, marksman laser telegraph ported from the M2->M3 idiom into STATE.m4_lasers, drawn in draw.py); the hold clock (M4_HOLD_SECONDS=90) is timer-driven and independent of wave state so it never soft-locks; a diegetic PA/arrest beat ladder in flow.py narrates Retardovici's order over pa_mumble/radio_static/footstep (C_RETARDOVICI/C_BALACEANU colors); spawns break off after the order airs; _complete_m4() sets request_mission4_ending. Biribel never sees or kills Balaceanu.
- W5 (Slice 4) ending + closure: new src/cutscenes/m4aftermath.py (_draw_m4_city_curfew/_draw_m4_arrest_screen/_draw_m4_maru_silhouette/_draw_m4_roof_dawn, surface,t idiom) dispatched from engine.py and re-exported from cutscenes/__init__.py (m3ending precedent); m4/meta.py intro/ending shot-lists replaced with real shots (m3_end_nation callback + title cards); the MISSION_COMPLETE card is generic (reads STATE.active_mission_* set by start_m4) so no per-mission branch was needed.
- W6 (Slice 5) verification + docs: smoke checks added mission4_boot_and_walk / mission4_stage_transitions / mission4_checkpoint_routes / mission4_hold_clock (laser queue + full 90s hold with all 5 arrest marks + concurrency cap) / mission4_ending_shots_render (each non-title-card scene headless-draws, std-dev guard) / mission4_campaign_chain (save->resume routing + checkpoint boots). Docs: MISSION4_PLOT.md beat sheet, LORE.md timeline M3/M4 rows + Maru physical-appearance note, this worklog entry, IMPLEMENTED.md Mission 4 section.
- Cross-package rule held: zero imports from missions.m3 internals; tuning/cadence/laser idioms copied with `# ported from` comments. Gate: compileall clean; SMOKE TEST: OK with all 6 mission4 checks green.

---
Task ID: m4-visual-parity-and-layout
Agent: Qoder
Task: Owner report - Mission 4 shipped looking like a placeholder next to M2/M3 (flat-rect world, never-drawn minimap, a hollow walkable "field" with walls you could walk through, text-strip HUD, rect/circle NPCs). Bring M4 to visual parity and rebuild both maps on a readable, properly-walled layout. Per-milestone gate: `python -m compileall -q src tools` (exit 0) + `python tools/smoke_test.py` (SMOKE TEST: OK).

- A+F layout (src/missions/m4/maps.py + meta.py): rewrote both generators on a solid-block grammar. The street defaults to solid "C" and the walkable map is negative space carved out of it - one E-W boulevard (rows 18-20) with "d" sidewalks, two cross streets, five full-height alleys, painted "R" lane centre, "B" curfew barricades the alleys detour around, a real safehouse shell (NW, "g" interior + "D" door) and a station door "D" at (31,19); route safehouse door -> boulevard -> station reads at a glance. Station interior: solid "C" with rooms carved as "O" floors + "L" corridors and "D" doorways. _WALKABLE_TILES gained "d"; _validate + M4_SOLID_CHARS kept in sync; new key tiles (PLAYER_START (9,4), VASILE_CACHE (16,21), STATION_DOOR (31,19)) and re-scoped zone rects.
- B+E entity/ tile art (src/missions/m4/draw.py): replaced the flat-rect floor/wall pass with a core.artpack sprite blit (walls via artpack.wall, floors via artpack.tile) ported from m3's _render_cell_bg (not imported). Marker chars resolve to their underlying floor (E/M/R->asphalt, V->sidewalk, station fixtures->interior floor); "D" gets a recessed frame + lintel; V/T/J draw prop sprites over their floor; a separate per-frame pulsing beacon pass keeps the bake deterministic. NPCs became facing-aware top-down figures (artpack.pose cache + faction color + contact shadow); pickups use artpack.icon (bandage) / a drawn magazine.
- C pipeline (draw.py + core/lighting.py): static-layer bake (_m4_static_layer / _bake_m4_static, sig keyed to id(MISSION4_MAP) so the street<->station swap invalidates); night lighting driven by a _m4_solid_world caster + st_/sn_ lamp tables over new m4street (cold sodium) / m4station (phosphor) grades, with motivated objective glow at the transmitter/jammer; shared sprite rain over the street only; a deterministic seeded world-ground dressing pass (tone blotches, wall-base contact shadow, sparse scuffs/chips) gated to open ground so the station stays clean. game_draw split into _game_draw_inner (world, baked when ACA_STATIC on) + a wrapper (begin_frame -> inner -> push_lights + composite -> rain -> scanlines -> HUD), so the HUD renders after the grade and stays legible. flow.start_m4 seeds STATE.rain_drops.
- D HUD parity (draw.py): the missing minimap is now drawn every frame (STATE.minimap.draw with a stage-aware objective marker); added a hostiles counter and a K-9/OS-12/sidearm magazine-icon weapon panel + a STAGE_COMMIT hold-the-transmitter clock plate, all ported from the M3 HUD language (values local, m3 not imported).
- Test plan: added tools/smoke_test.py check_mission4_layout (street solid fraction proves blocks not a field; flood-fill PLAYER_START->STATION_DOOR and STATION_START->TRANSMITTER; no objective key on a solid char). Gate: compileall clean; SMOKE TEST: OK (exit 0) with all 7 mission4 checks green, including the 6 pre-existing boot/transition/checkpoint/hold/ending/campaign invariants unchanged on the new maps.



## Internet tunnel correction (2026-10-09)

- Replaced invalid direct-Cloudflare TCP assumption with bundled bore v0.6.0.
- Added pinned official Windows x64 downloader, archive/executable SHA-256 checks,
  MIT licence, build integration, and shared CLI/arena tunnel startup.
- Added atexit child cleanup for normal exits/unhandled Python exceptions,
  bounded startup waiting, drained post-start logs, and process reaping.
  Force-kill/native crashes are not covered by atexit.
- Focused unit checks and real local/public bore TCP echo round-trips passed.
- Full smoke suite blocked by missing pygame in this sandbox. Windows builds
  and two-device arena gameplay are not tested.

## Internet tunnel pass 2 (2026-10-09)

- Tunnel start is cancellable: `start_tunnel(..., cancelled=callable)` stops a
  pending bore/ngrok start within ~0.25 s and skips the ngrok fallback.
- MatchScreen passes a host-token cancel check; worker publish and teardown now
  hand off `_tunnel_proc` under `_tunnel_lock`, closing a LEAVE-during-publish leak.
- Relay loss: `_check_tunnel_alive()` (each host update) detects a dead relay
  process, drops the stale public invite, reverts to the LAN code and tells the
  host to host again. Added status lines for "tunnel lost" and "bore missing".
- Smoke: mocks updated for the new `cancelled` argument; added relay-loss and
  startup-cancellation checks inside check_mp_host_and_portmap (pass).
- Full smoke with pygame-ce 2.5.8/moderngl 5.13/numpy 2.5.3 (Linux, dummy SDL):
  103 OK, 1 SKIP (GL, no libGL), 2 FAIL unrelated to tunnelling:
  join_loopback_fallback (sandbox accepts TCP to 10.255.255.1; env artefact) and
  mission4_cinematic_arrest (test expects exact fired_cues; app.py also records
  (shot, "vo")). Both failures were identical before this pass's edits.
- Linux PyInstaller probe (not Windows): bundled bore found inside _MEIPASS when
  run from /tmp with empty PATH; public bore.pub echo PASS; 0 processes left.
- Windows EXE build and two-device gameplay still NOT tested.

## Mission 5 - W4 (Integration) (2026-10-09)

- `core/game_core.py`: imports `missions.m5` and adds it to `_MODULES` (so
  `gc.mission5_intro_shots` / `gc.mission5_ending_shots` / `gc.request_mission5_ending`
  resolve through the proxy); `_is_mission5_active()`; `start_mission5()` /
  `start_mission5_printworks_checkpoint()` / `start_mission5_tunnel_checkpoint()`
  wrappers (all `_fresh_audio`-wrapped); MISSION5 is checked BEFORE MISSION4 in
  `game_update` / `game_draw` / `handle_interact` / `debug_jump_to_exfil` (no-op,
  same as M4); the restart ladder puts the tunnel checkpoint above the print
  works above the Lower Quarter.
- `app.py`: `--dev-mission5` (bulletin chain -> after="MISSION5"),
  `--dev-mission5-game`, `--dev-mission5-printworks`, `--dev-mission5-tunnel`;
  slot resume `last=="MISSION_4"` -> M5 intro chain, `last=="MISSION_5"` ->
  FULL CAMPAIGN COMPLETE, `progress=="m5"` -> deepest checkpoint;
  `_CutsceneState._handle_end` after=="MISSION5" / "MISSION5_COMPLETE";
  GAME-state dialogue keys route to `m5.handle_dialogue_event` while
  `STATE.m5_dialogue_active`; `request_mission5_ending` ->
  `mission5_ending_shots` with after_state "MISSION5_COMPLETE";
  `_MissionCompleteState` chains MISSION4 -> M5 intro (MISSION5 -> menu);
  GAME ambience is stage-aware for M5 (rain+wind on the quarter only - the
  print works and tunnel are indoors; M5 is deliberately NOT in
  `ambience.RAIN_MISSIONS` so the roof-rain bed never follows the player
  underground).
- `core/dev_jumps.py`: m5 / m5-game / m5-printworks / m5-tunnel.
- `core/save_system.py`: `_MISSION_RECORDS["MISSION5"]` -> `MISSION_5`,
  "Mission 5 - Martial Law", full prerequisite flags through
  `mission5_complete`.
- Smoke: `check_mission5_integration` (boot via gc, sentinel-proven routing,
  restart ladder, Maru-fail -> death screen -> tunnel respawn, save record,
  dev-jump registry, progress marker, app.py/game_core source contract) and
  `check_mission5_cutscene_shots` (shot lists resolve through the facade and
  paint without raising; bespoke m5_* art is W5). Full smoke: OK.
- Verified live with a frame-capture harness: `--dev-mission5-game`,
  `--dev-mission5-printworks`, `--dev-mission5-tunnel` and `--dev-mission5`
  all boot through the real app loop (shots/m5_w4/).

## Mission 5 - Maru re-skin (post-W4 review, 2026-10-09)

- `m5/draw.py._draw_maru` drew Maru as a rotated green disc + head circle -
  fine for anonymous troopers, wrong for a named character the player escorts
  for two stages. Replaced with the cutscenes.figure_kit "maru" cast rig (the
  same black hoodie / shag hair / backpack look M4 paints at the station meet
  and W5 will use in the river-gate scene), ported from m4's kit-pose math:
  3x supersample -> smoothscale into an artpack.pose cache keyed by
  (angle, hit-flash), pistol rig rotates with facing, body stays upright.
- Wounded arm: sleeve down Maru's LEFT figure side (flips with facing like the
  kit's own limbs) ending in a white bandaged hand; hit flash strobes the coat
  to red via the draw_character wardrobe override. First pass had a diagonal
  strap across the chest that read as a baldric - removed.
- Facade exports `_maru_pose`; verified against M4 with a pose sheet
  (shots/m5_w4/maru_compare.png) plus in-game zooms (maru_zoom.png). Full
  smoke still OK. mission5-W4.zip rebuilt to include draw.py + __init__.py.

## Mission 5 - W5 (Cutscenes) (2026-10-09)

- New `src/cutscenes/m5martial.py`: eight bespoke 2D scenes in the
  m4aftermath idiom (composition inside SAFE_TOP..SAFE_BOT, helpers imported
  from m3ko/m3cell/chair/route12, every named figure via cutscenes.cast):
  intro = m5_tv_bulletin (state studio read + chyron + echo monitor),
  m5_safehouse_tv (Biribel at the rainy window, back to a CRT playing the
  bulletin), m5_retardovici_tv (podium/seal/twin flags/crowd address);
  ending = m5_river_gate (Maru through the bars, red scope dot arriving on
  Biribel), m5_ucilev_scope (reticle optic with mil-dots + RANGE/WIND HUD,
  breath sway settling), m5_ucilev_reveal (Guard black + red armband, rifle
  lowering), m5_ucilev_leaves (walking off into rain toward the gate lamp),
  m5_radio (split-frame quay <-> Vasile's office with the new flag).
- `cutscenes/engine.py`: import the eight _draw_m5_* fns and dispatch their
  scene names in draw_cutscene_scene's chain (after m4_roof_dawn).
- Smoke: check_mission5_cutscene_shots upgraded from the W4 lit-backdrop
  tolerance to the M4 tonal-spread bar (std-dev > 3.0 at t=0/1500/4000/9000
  for every non-title shot) + the scene-name set assertion. Caught one real
  regression: the radio tag used U+2194 (↔), missing from oswald -> tofu;
  switched to ASCII "<->". font_glyph_coverage now passes again.
- Verified live: --dev-mission5 intro plays the bulletin chain through the
  real app loop with the ANCHOR dialogue box over it (shots/m5_w5/intro_f*.png);
  per-scene full-res renders in shots/m5_w5/. Fixed a bezel-fill bug that was
  painting the safehouse CRT flat before the feed blit. Full smoke: OK.

## Mission 5 - finale stabilisation (2026-10-13, Arena session)

Baseline after unpacking `First try-slim.zip`: `SMOKE TEST: FAILED` (129 OK /
3 FAIL / 1 SKIP) plus two live crash reports from 16:04
(`m5shadow3d.armed_pose -> ValueError: No reachable two-handed rifle pose`,
frame 26 of the finale). Root cause of all of it: the last session moved the
weapon foregrips forward and rewrote Ucilev's hold around an exact two-bone
solver (`_weapon_arm`) but left Biribel on the old clamped per-hand `_solve`
path (support hand ~20 cm off the K9) and left the checks pinned to the
previous choreography.

- `cutscenes/m5shadow3d.py`: ONE two-handed solver for both actors
  (`_two_handed_pose`, ex `_sniper_pose`; `_clear_lowering` flag gone). The
  whole weapon is moved into the shared reach of both arms, trigger hand
  solved exactly, support hand onto `hum._foregrip` in the rifle frame
  (0.000 mm contact error over the film + an aim/lower grid). `_weapon_arm`
  can no longer raise: out-of-reach targets clamp to `_ARM_REACH` (.600, elbow
  never locks) and a degenerate elbow pole falls back to the next pole - a
  cutscene frame must never take the game down. `UC_STRIDE`, `LOWER_DIP`,
  `LOWER_DROP` named so the checks derive from them. `_sky` rounds instead of
  truncating (horizon row == fog again). Subtitles moved out of `draw()` into
  `draw_controls(s, paused, confirm, t)` because the app paints the letterbox
  AFTER the scene; the controls hint moved to the top band.
- `cutscenes/engine.py draw_cinematic_subtitle`: centred in the bottom
  letterbox band (never over the picture), one font, speaker as an inline
  accent-coloured prefix (radio convention, no header strip per T8), layout
  from the full text; `app.py` passes `t_ms` to `draw_controls`.
- `tools/m5_shadow_check.py`: contact against the per-actor foregrip (+ an
  aim x lower envelope sweep), planted-foot window derived from
  `STANCE*UC_STRIDE`, head-safe samples follow the current cuts (withdrawal
  covers Ucilev to `UC_RETREAT_END`, then the radio shot covers Biribel; x
  checked too), two-stage lowering asserted from `LOWER_DIP/LOWER_DROP` and
  monotonic.
- `tools/m5_harbour_art_check.py`: EXPECTED_MOTION re-pinned to the current
  (intentional) choreography; docstring documents when/how to re-pin; the
  failure message names the drifted function.
- `missions/m5/inspect_art.font()`: bundled IBM Plex Mono Bold / Oswald
  (emboldened) instead of SysFont consolas/impact - the inspect-shot bakes
  were machine-dependent (4 of 6 differed on any box without those fonts).
  Rebaked `assets/sprites/m5/`: only `tram_wreck_0` (stale 5x7 graffiti) and
  `inspect_art_{0,2,3,5}` changed, 120 other files byte-identical.
- `tools/m5_laser_stair_check.py`: mock signature caught up with
  `_laser_sight(..., power)`.

Gate: `python -m compileall -q src tools` OK; `python tools/smoke_test.py`
-> `SMOKE TEST: OK` (134 OK, 0 FAIL, GL SKIP as always headless). Standalone:
`m5_shadow_check.py`, `m5_harbour_art_check.py`, `m5_laser_stair_check.py`,
`m5_stair_room_check.py`, `m5_finale_cut_check.py` all OK. 5044 actor frames
stepped at 60 fps (both reduced-motion settings) without an exception.
Not touched: `tools/finale_gait_check.py` is a print-only probe whose
"stance drift" heuristic misreads double support; Maru's gait is unchanged.

## RPE6 - Phase 0 + Phase 1 closeout (2026-10-14, Arena session)
Plan of record: `docs/engine/STATUS.md`; reports `docs/engine/reports/phase0.md`,
`phase1.md`; deliberate changes `docs/engine/CHANGELOG.md` (M1-M3); no git in
the sandbox, so this is the changed-files log.
- M1 oracle + tooling: `tests/unit` rewritten (43 tests), sandbox baselines
  captured (golden 353, replay 5 segments, loop 7 segments), B-012 radio-cache
  RNG leak fixed (`audio/voice.py`), the 5 new W1 edges removed
  (`core/cutscene_registry.py`, `missions/m5/finale_audio.py` ex
  `audio/m5_finale.py`, `AudioManager.register_lazy_generators`).
- M2 Phase 0 exit: `tools/ae_normalize.py --mojibake --apply` -> 90 files LF/
  UTF-8 (46 .py AST-identical), `.gitattributes`, B-003 mojibake repaired
  (13 lines left in `missions/m2/draw.py`). Gate identical before/after.
- M3 Phase 1 exit: `engine.core.Clock` frame-coherent wall clock + `engine.core.
  now_ms/now_s` (adapter A-004, ADR-005); `tools/ae_migrate_time.py` moved 163
  `get_ticks` + 48 `time.time` reads in 33 modules (AST proof); `app.py`
  feeds the clock after `display.flip()`. `GRAIN_VARIANTS` on the named
  `grain` stream -> loop `baseline_v2` (states identical; v1 kept). 34 unused
  `import random` dropped. B-011 withdrawn (was B-012). Check tools pin the
  engine clock (`pin_wall`): smoke_test (2 checks + death screen),
  k9_pickup_check, m5_finale_cut_check, m5_shadow_check, render_m4_ending,
  shot_fail_screens; `tools/sprites/portraits.py` adds `src/` to sys.path.
Gate: `python tools/ae_ci.py` -> `AE CI: OK` (compileall, boundaries 169/169,
import check, 43 unit tests, `SMOKE TEST: OK`, golden 353/353, replay 5/5,
loop 7/7). Owner to-do: `git add --renormalize .`, re-capture `tests/` on the
reference machine.

## Housekeeping - project trimmed to fit the 128 MB sandbox cap (2026-10-14)
114 MB -> 73 MB. Deleted (regenerable or redundant): `assets/voice/_radio_cache/`
(9.5 MB runtime cache, now in .gitignore), `crash_reports/` (old dumps; the
engine recreates the folder), `assets/voice/Old Fisherman/` (7 wavs byte-
identical to `VO_185..191.wav`, which the game uses; the loader ignored the
folder - voice match tables verified identical before/after), one duplicate
JPEG in `handoff/`. Deleted (owner's choice, unreferenced): `icon_ai.png`,
`wordmark.png/.html`, `handoff/`, `SKILLS/` + the Notion prompt export,
`apply_*.py`, `_inspect2.py`. Deleted (owner's choice): the 353 golden PNGs in
`tests/golden/baseline_v0/` - `manifest.json` keeps the sha256 per shot and
`ae_golden.py verify` passes from it (ADR-006). Moved to `docs/history/`
(not deleted): old agent brief, fix-pass notes, Mission 5 wave READMEs,
patch notes and the now-stale checksum manifests; `VALIDATION.md` ->
`validation/M5_harbour_graphics.md`. Kept: `assets/voice/Trailer/` (trailer
tool input), the five zero-byte casting notes in the root. Gate after:
compileall OK, 43 unit tests OK, golden 353/353 OK, replay 5/5 OK, smoke OK.

## Asset diet (2026-10-14, Arena session, owner request)
73 MB -> ~26 MB. Voice WAV -> OGG Vorbis (~77 kbps; mixer is 22.05 kHz so
nothing audible is lost; `tools/convert_voice_ogg.py`, verified frame counts,
match tables, silent tails). `voice._duration` gained an Ogg header reader so
the start-up scan stays instant. `assets/bg.jpg` (really a 1.3 MB PNG) -> real
1000x700 JPEG q90 (130 KB), reviewed side by side. Trailer-only material
deleted (sfx_wav/, assets/voice/Trailer/, assets/music/trailer/) plus the
duplicate root icon.png. Loop baseline -> `tests/loop/baseline_v3` (menu frames
+ subtitle end frames; states identical 7/7). Full gate green afterwards (see
docs/engine/CHANGELOG.md for the evidence).
- Follow-up: subtitle/duck timing restored to the WAV-era millisecond
  (`voice._clip_ms` emulates SDL's WAV sizing from the OGG header; unit test
  `tests/unit/test_voice_timing.py`). Loop v3 vs v2: only boot (menu bg) and
  m3 frame 151 (radio LED ladder, decoded clip ends in silence 12-33 ms
  earlier) differ.

## 2026-10-14 — Phase 2 start (P2-M1..M3)
- `src/engine/scene/` (Scene, SceneStack) + 11 unit tests; `core/fsm.py`
  `on_change` observer; `core/scene_mirror.py` (A-005); `app.py`
  `_LegacyGameScene` owns the stack. Loop probe records/compares `scene_trace`
  (baseline_v3 gained the key additively, hashes/states unchanged).
- `tests/data/m5_scene_trace.txt` + `tests/unit/test_scene_mirror.py` (M5 FSM
  flow through the real GameStateManager).
- `tools/ae_api_snapshot.py` + `tests/api/engine_api.json`; `ae_ci.py` gained the
  "api snapshot" row (16 modules, 79 names).
- Gate: `/tmp/ci_p2m1.txt`.
- P2-M4a take registry: 58 dispatcher branches moved to per-module
  `register_scene_renderers` tables (m3cell/m3ops/m3ko/m3broadcast/m3ending/
  m4aftermath/m5martial3d/chair + missions/m3/draw.py); `cutscenes/engine.py`
  imports no mission take module any more; W1 169 -> 114 (`BASELINE_W1`);
  smoke check `cutscene_scene_ids_resolve`. Gate: `/tmp/ci_p2m4.txt`.

## 2026-10-14 — Phase 2 close (P2-M4b..M6)
- `engine/scene/cutscene.py`, `inspect.py` (+ facade); `core/scene_mirror.py`
  `scene_factory`; `missions/m5/inspect_fpv.py` `on_change`; `app.py`
  `_LegacyGameScene._scene_for/_on_inspect` (A-007).
- Module moves (A-006): `engine/render2d/`, `engine/lighting/`,
  `engine/assets/` (`_artpack.py`, `_sprites.py`), `engine/anim/`; shims at
  `core/render_util.py`, `core/lighting.py`, `core/artpack.py`,
  `entities/sprite_lib.py`, `cutscenes/figure_kit.py`. Backups of the originals
  were taken to /tmp only (bodies are verbatim in the engine files).
- `cutscenes/__init__.py` trimmed (no mission take re-exports);
  `missions/m3/draw.py` imports `cutscenes.m3cell` directly; explicit take
  imports in `missions/m3/meta.py`, `missions/m4/draw.py`, `missions/m5/meta.py`.
  `BASELINE_W1` 114 -> 48.
- `tools/ae_api_snapshot.py` describes module-valued exports; snapshot
  re-recorded (25 modules / 121 names).
- Tests: `tests/unit/test_scene_types.py`, `test_engine_shims.py`;
  `test_voice_timing.py` pins the mixer rate.
- Docs: ADR-014, ADAPTERS A-006/A-007, BUGS B-013, `reports/phase2.md`,
  CHANGELOG, STATUS. Gate: `/tmp/ci_phase2.txt` (`AE CI: OK`).

## 2026-10-14 — RPE6 Phase 3 (one shot) + Phase 4 prep
- New: `src/engine/assets/{manifest,registry,bake,watch,loaders}.py`
  (facade `engine/assets/__init__.py` re-exports), `src/engine/anim/pose_cache.py`
  (`engine/anim/__init__.py` exports `PoseCache/POSES/POSE_CAP`;
  `engine/assets/_artpack.py` `pose()` delegates, `rebuild()` clears it).
- Moved: `src/art/m5/*.py` (20 sprite modules + `_kit.py`) → `src/game/art/m5/`
  (intra-package imports rewritten to `game.art.m5`); `assets/sprites/m5/*.png`
  (125) → `assets/baked/m5/` (+ `.bakeinfo.json`). New `src/game/__init__.py`,
  `src/game/art/__init__.py`, `src/game/art/m5/__init__.py` (owner registry
  wrapper), `src/game/content/__init__.py`, `src/game/content/m5/manifest.json`,
  `src/game/content/m5/palette.json`. `src/art/m5/__init__.py` rewritten as the
  A-008 shim (sys.modules aliases). `game/art/m5/inspect_art.py` declares
  `BAKE_DEPS`.
- Edited (D5 rerouting, same arguments): `src/core/config.py`, `src/ui/radio.py`,
  `src/ui/hud.py`, `src/missions/m3/draw.py`, `src/missions/m5/finale_audio.py`,
  `src/audio/voice.py` (6 sites), `src/audio/audio.py` (3 sites).
- Edited: `src/app.py` (`_rpe6_hot_reload()` + one poll line, env-gated),
  `tools/ae_audit.py` (`MISSION_RE` += `game\.art\.m\d`), `tools/ae_ci.py`
  (bake row live), `tools/smoke_test.py` (`check_mission5_sprites` rewritten),
  `tools/sprites/kit.py` + `palette.py` (kit path), `tools/m5_sprite_review.py`,
  `tools/build_all_sprites.py` (doc line), comment paths in
  `missions/m5/{draw,inspect_fpv,inspect_art,tram_wreck,decor_interior}.py`.
- Tools: new `tools/ae_bake.py`, `tools/ae_draw_audit.py`,
  `tools/ae_star_imports.py`, `tools/ae_hud_census.py`; `tools/bake_m5_sprites.py`
  and `tools/m5_draw_audit.py` reduced to wrappers.
- Tests: `tests/unit/test_assets_registry.py` (20); API snapshot re-recorded
  (31 modules / 169 names, additive).
- Docs: ADR-015, ADAPTERS A-008, BUGS B-014..B-016, CHANGELOG "Phase 3",
  `reports/phase3.md`, STATUS, `audit/draw_census.md`, `audit/star_imports.md`,
  `audit/hud_duplication.md`. Gate: `/tmp/ci_phase3.txt`.
- Not done: ≥ 80 % procedural-draw conversion for M1–M4 (B-016).

## 2026-10-14 — Phase 3 follow-up: Tier A world layers for M1–M4 (owner mandate "convert everything convertible")

- Engine: `src/engine/assets/layerbake.py` (new), `bake.py` (`bake_setup` hook), `registry.py` (layer LRU,
  24-bit opaque layers, `evicted` stat), `__init__.py` (facade exports).
- Game art: `src/game/art/_layers.py` (new), `_pack.py` (`blit_layer`, `layer_variant`),
  `src/game/art/m3/{cell_details,cellblock_static,archives_static,comms_static,broadcast_static}.py`,
  `src/game/art/m1/world_static.py`, `src/game/art/m2/world_static.py`, `src/game/art/m4/world_static.py`;
  manifests `src/game/content/m{1,2,3,4}/manifest.json`; baked `assets/baked/m{1,2,3,4}/`.
- Missions: `src/missions/m3/draw.py` (call sites, `_draw_m3_static_live`, `_draw_archives_wing_live`,
  `_draw_broadcast_wing_live`, `baking()` guards), `src/missions/m2/draw.py` (call site, `_draw_shelter_live`),
  `src/missions/m1/draw.py` (call site), `src/missions/m4/draw.py` (call site, `_stable_seed`, B-017).
- Tools: `tools/ae_layer_parity.py` (new), `tools/ae_layer_probe.py` (new), `tools/ae_bake.py` (pins),
  `tools/ae_loop.py` (baseline v4 + header note).
- Tests: `tests/golden/baseline_v0/gp.m4.street{,_east}` re-captured (evidence
  `docs/engine/evidence/m4_stable_seed/`), `tests/loop/baseline_v4/` (m3, m4 re-recorded; rest copied),
  `tests/api/engine_api.json` re-recorded (additive).
- Docs: BUGS B-017, CHANGELOG, ADR-015 addendum. Gate `/tmp/ci_tierA.txt` = `AE CI: OK`.

## 2026-10-14 — Phase 3 follow-up, Tier B (M3 KO / neighbour cells / kitchen layers; sprites M1–M4; M4 station dressing)
- Engine: none (uses the Phase 3 `engine.assets` API as is).
- Game art adapters (new): `src/game/art/m3/{ko_static,kitchen,door_tile,weapon_icon,cell_door_blown,wall_monitor,pickup_icon,camera_body}.py`,
  `src/game/art/m2/{prop_icon,nest_bits}.py`, `src/game/art/m1/{molotov_icon,pickup_icon,exfil_truck}.py`, `src/game/art/m4/mag_icon.py`;
  `src/game/art/m3/cellblock_static.py` rewritten (4 variants, neighbour cells inside). Manifests `src/game/content/m{1,2,3,4}/manifest.json`;
  baked `assets/baked/m{1,2,3,4}/` (+`.bakeinfo.json`); `assets/baked/m3/neighbor_cells_*` deleted (abandoned transparent layer).
- Missions: `src/missions/m3/draw.py` (KO split + `_bake_m3_ko` + layered `_game_draw_kill_order`; neighbour cells static/live split,
  `_neighbor_cell_stains`, `_NC_TUBE_STAINS`, `_draw_neighbor_cell_tube`, `_draw_remains_cell_scraps`, `_draw_neighbor_cells_live`; kitchen call site;
  `_paint_cell_door_{jambs,blown,blast_damage}`, `_cell_door_settled_variant`; `_paint_wall_monitor_part`; `_paint_m3_pickup_icon`),
  `src/missions/m3/systems.py` (`_m3_door_tile_state`, `_paint_m3_door_tile`, `_paint_m3_weapon_icon`, `_paint_security_camera_body`, `_m3art` import),
  `src/missions/m2/draw.py` (`_PROP_ICON_*`, `_prop_icon_variant`, `_draw_prop_icon_live`, `_paint_prop_icon`, `_nest_bit`, `_paint_nest_bit`),
  `src/missions/m1/draw.py` (`_paint_molotov_icon`, `_M1_PICKUP_VARIANTS`, `_paint_m1_pickup_icon`, `_paint_m1_exfil_{truck,headlights}`),
  `src/missions/m4/draw.py` (`_bake_m4_static` + station dressing, `_m4_mag_icon_variant`, `_paint_m4_mag_icon`).
- Tools / tests: `tools/ae_golden.py` (+6 M3 stills, `tests/golden/baseline_v0/gp.m3.{kitchen,ko_*,cell_*}`; manifest 373 shots). No baseline re-captures.
- Docs: CHANGELOG (Tier B), ADR-015 addendum (2), BUGS B-016, reports/phase3.md outcome, STATUS next steps, audit/draw_census.md.
- Evidence: `docs/engine/evidence/tierB/ci_tierB.txt` = `AE CI: OK`; `docs/engine/evidence/tierB/m3_sprite_parity.txt`, `docs/engine/evidence/tierB/m124_sprite_parity.txt` (max Δ 0).

## 2026-10-15 — Sandbox re-import (owner zip 117 MB / 2038 files) + slimming + API snapshot platform fix
- Removed from the sandbox copy with `tools/slim_tree.py --apply` (new; dry run by default): 175 voice `.wav` twins of the
  shipped `.ogg` takes (45.3 MB), 51 orphan golden PNGs not in `tests/golden/baseline_v0/manifest.json` (5.9 MB, stale
  `cut.m5.M5_MID_CUTSCENES.*` ids), `tests/golden/_verify/`, `sfx_wav/`, `assets/voice/Trailer/`, `assets/music/trailer/`,
  `assets/voice/Old Fisherman/`, `handoff/`, `SKILLS/`, root `icon.png`, `apply_*.py`, `_inspect2.py`, and the superseded
  `tools/overlay_cleanup.py` (its manifest no longer exists; it would have deleted post-Phase-4 modules). 138 → 79 MB on
  disk, zip 117 → 67 MB. Nothing under `src/`, `docs/`, `assets/baked|art|sprites`, `tests/unit|api|loop|replay` touched.
- `tools/ae_api_snapshot.py`: `_type_name()` (pathlib classes → `Path`), `tests/api/engine_api.json` 2 entries normalised (B-028).
- Gates on this tree (Linux, pygame-ce 2.5.8): compileall OK, smoke OK, units 180/180, `AE API: OK`, `AE BAKE: OK`
  (42 assets, 0 stale), `BOUNDARIES: OK` (W1 48), `AE TEXT: OK`, replay 5/5. Reference-machine pixel oracles differ here as
  documented (golden 365/373, loop 2/7) — sandbox baselines must be captured separately before any sandbox parity work.
- Second pass (owner: "delete useless stuff"): `tools/slim_tree.py` now also removes root duplicates of notes already in
  `docs/history/` (`FIXES.md`, `IMPLEMENTED.md`, `MASTER_PROMPT.md`, `manifest.json`, `MULTIPLAYER_PATCH_SHA256.json`;
  `VALIDATION.md` = `validation/M5_harbour_graphics.md`), the unreferenced `icon_ai.png` / `wordmark.*` / Notion export /
  `tools/_tmp_repl.json`, and loop history older than the newest two sets (`tests/loop/baseline_v0..v3`; v4 + v5 stay;
  `ae_loop.py` header note updated). Applied here: 15 entries, 2.3 MB. Kept on purpose: `tools/golden.{py,json}` (the smoke
  test calls `compare()`), `validation/`, `docs/history/`, `build.bat`, and the ~90 one-off scripts in `tools/`
  (trailer / multiplayer / M5 review) - owner call.


## 2026-10-15 — Phase 5 (world + standard systems) P5-M1…M4: sandbox oracles, `engine.world` kernel, legacy bridge, D4 for M5
- New: `src/engine/world/` (`__init__.py` facade, `_component.py` registry + `schema/to_dict/from_dict`, `entity.py` World, `system.py`
  Scheduler PRE/SIM/POST/RENDER_SUBMIT, `prefab.py` JSON `extends`, `std.py` Transform/Health/AIBrain/Faction/Collider/Label/Lifetime/Tags/
  `WalkCycle` (+`primed`, `advance()`)/HitFlash/LegacyRef); `src/game/world/` (`__init__.py` owner: install/reset/pre_update/post_update/
  render_submit/`entity_of`/`get`/`ensure`; `legacy.py` views + `LegacyRoster` register_now/check_reset/sync/removed-tag/clear);
  `src/missions/m5/components.py` (`M5Guard`); `tools/ae_dump_components.py`; `tools/ae_d4_gate.py` (+ `docs/engine/evidence/phase5/d4_baseline.json`);
  `tools/ae_d4_replay_compat.py` (evidence tool, temporary); `tests/unit/test_engine_world.py` (17), `tests/unit/test_game_world_bridge.py` (7);
  `tests/replay/baseline_v1/` (snapshot v2, B-029); `tests/golden/sandbox_linux`, `tests/loop/sandbox_linux` (machine-local, now scratch in `slim_tree.py`).
- Changed: `tools/ae_golden.py` (`ACA_GOLDEN_SET`), `tools/ae_loop.py` (`ACA_LOOP_SET`), `tools/ae_replay.py` (`~world` field, version 2, default set
  `baseline_v1`), `tools/slim_tree.py`, `tools/smoke_test.py` (M5 start check reads `M5Guard`), `tools/m5_encounter_review.py`, `tools/m5_r2_check.py`;
  `src/core/game_core.py` (world host: `_gw.install` at mission start, `pre_update/post_update` around the inline dispatch chain, `render_submit`);
  `src/entities/enemy_ai.py` (class-level declared `is_commander/is_ambush_enemy/is_evidence_wave/is_breach_enemy/fire_weakness/sight_mul/_dt_mul`,
  `self.walk = WalkCycle()`, 9 `getattr` reads → direct, sway → `walk.advance`), `src/entities/weapons.py` (6 reads direct), `src/entities/corpse.py` (3),
  `src/entities/player.py` (`story_outfit/_outfit_rk` declared), `src/missions/m1/{update,main}.py` (`is_commander` direct),
  `src/missions/m5/{quarter,world,draw,systems}.py` (37 `m5_*` sites → `_m5g(e).<field>`; `draw.py` walk cycle), `src/missions/m3/systems.py:1935`
  (`hasattr(e, "_apply_move")` dropped), `tests/api/engine_api.json` (recorded: 53 modules / 320 names), `docs/engine/{STATUS,BUGS}.md` (B-029).
- Gates (Linux sandbox, `ACA_GOLDEN_SET=ACA_LOOP_SET=sandbox_linux`): replay 5/5 (`baseline_v1`) + v0 compat proof 150/150
  (`docs/engine/evidence/phase5/m4_replay_compat.txt`), golden 373/373, loop 7/7, `SMOKE TEST: OK`, units 204/204, `BOUNDARIES: OK` (W1 48 =),
  `AE API: OK`, `AE D4: OK (hard=0, remaining mission-prefixed sites=76)`, dump tool: `M5Guard` 7 + `WalkCycle` 7 on the quarter stage.
- `assets/baked/m3/.bakeinfo.json` re-recorded (`ae_bake.py --pack m3`): the one-line `m3/systems.py` edit changed the source hash of 4 painters;
  all 32 PNGs byte-identical (md5 before/after), `AE BAKE: OK`. Gate log: `docs/engine/evidence/phase5/m4_gate.txt`.
- Not done: D4 for M1–M4 (76 ratcheted sites), systems (P5-M6), phase report/ADR (P5-M7). Owner note: `tests/golden|loop/sandbox_linux` must not be merged.

## 2026-10-15 — Engine renamed + Phase 5 P5-M5: D4 for M3/M4/M2
- **Rename (owner request): "Retardovici Pulse Engine 5 / RPE5" → "Retardovici Pulse Engine 6 Gold / RPE6"** everywhere (156 files, 323 byte-level
  replacements: `Retardovici Pulse Engine 5`→`… 6 Gold`, `RPE5`→`RPE6`, `rpe5`→`rpe6`; `src/engine/__init__.py` `ENGINE_NAME`/`LOG_PREFIX`, crash-report header,
  `tests/unit/test_app_boot_crash.py`, `docs/engine/*` incl. the master prompt's naming line, `AGENTS.md`, `.gitattributes`, `app.py` `_rpe6_*` identifiers).
  Line endings/encodings preserved (byte replace). `__version__` 0.1.0 unchanged. Not done (not wired before either): the engine name in the window
  title / splash / credits - the game title is "Call of Acaristan"; owner call. The copy in `/home/user/uploads/ENGINE_MASTER_PROMPT(2).md` is untouched.
- New: `src/missions/m3/components.py` (`M3Guard`), `src/missions/m4/components.py` (`M4Guard`), `src/missions/m2/components.py` (`M2Role`);
  `docs/engine/evidence/phase5/m5_replay_compat.txt`.
- Changed: `src/missions/m3/{world,systems,sweep,draw,__init__}.py`, `src/missions/m4/{world,systems}.py`, `src/missions/m2/{world,sniper,update,starts}.py`
  (75 `m3_*`/`m4_*`/`is_mission*`/`shield_angle_width` sites → `_mNg(e).<field>` / `_mNl(e).kind|text`), `src/entities/corpse.py` (reads the shared `Label`
  component via `game.world.get`), `src/tools/ko_playability_audit.py`, `src/game/world/legacy.py` (selective `check_reset`, B-030), `tools/smoke_test.py`
  (3 mirrors read components), `tools/ae_d4_replay_compat.py` (per-segment legacy maps), `tests/replay/baseline_v1/` (re-recorded after the proof),
  `tests/golden/sandbox_linux/` (recaptured; `RECAPTURE.txt` corrected to `capture`), `assets/baked/{m1,m2,m3,m4}/.bakeinfo.json` (source hashes after the
  rename; all PNGs byte-identical by md5), `docs/engine/{STATUS,BUGS}.md`.
- Gates (`docs/engine/evidence/phase5/m5_gate.txt`): replay 5/5 (v1), compat 150/150 (v0), golden 373/373, loop 7/7, `SMOKE TEST: OK`, units 204/204,
  BOUNDARIES OK (W1 48 = after routing the audit tool's helper through its already-imported `_sweep_mod`), AE API OK, AE D4 OK (0 remaining), AE BAKE OK, AE TEXT OK.

## 2026-10-15 — Phase 5 P5-M5b: D4 for doors (`M3Door`) and the arena sprite state
- Changed: `src/missions/m3/components.py` (+`M3Door`), `src/missions/m3/{world,systems,sweep,draw,flow,interrog}.py` (38 `door.m3_*` sites → `_m3d(d).<field>`),
  `src/tools/ko_playability_audit.py` (`_sweep_mod._m3d/_m3g`, no new import names → W1 stays 48), `src/game/world/legacy.py` (`DoorTransformView`,
  `_spawn_door`, `STATE.doors` in `sync`, duck-typed `register_now` branch), `src/ui/arena_view.py` (`_PoseMeta` per slot; `Player` no longer stuffed),
  `tools/smoke_test.py` (`_m3door(d)`, arena reload-clock mirror reads `_view_meta`), `tools/ae_replay.py` (`~world` walks enemies + doors),
  `tools/ae_d4_replay_compat.py` (injects over every registered object; `M3Door` map), `tools/ae_d4_gate.py` (ratchet over any non-STATE receiver, calls
  excluded, `v` entity-like, no file exclusions), `tests/unit/test_game_world_bridge.py` (+2), `tests/replay/baseline_v1/` (re-recorded),
  `assets/baked/m3/.bakeinfo.json` (re-hashed; PNGs byte-identical), `docs/engine/evidence/phase5/m5b_replay_compat.txt`, STATUS.
- Gates (`evidence/phase5/m5b_gate.txt`): replay OK, golden 373/373, loop 7/7, smoke OK (two smoke mirrors updated: `volkov_foreshadowing` door filter,
  `mp_host_and_portmap` muzzle timer), units 206 OK, BOUNDARIES OK (W1 48 =), API +0/-0/~0, AE D4 OK (0), BAKE OK (m3 re-hashed), TEXT OK, D4 compat OK.

## 2026-10-15 — Phase 5 P5-M6/M7: hosted SIM system, ADR-016, phase report, CI rows
- Changed: `src/game/world/legacy.py` (+`LegacyMissionSystem`), `src/game/world/__init__.py` (+`step()`, host installed; `__all__`),
  `src/core/game_core.py` (`game_update` → `_gw.step(_mission_update)`; mission check order unchanged), `src/ui/arena_view.py` (reload-progress
  expression simplified to `meta.reload`), `tools/ae_ci.py` (+ rows `d4`, `dump`), `tools/smoke_test.py` (mirror `mp_host_and_portmap` → `_view_meta`),
  `tests/unit/test_game_world_bridge.py` (+`HostedStepTests`, 208 total), docs: `reports/phase5.md`, `adr/ADR-016-legacy-world-bridge.md`,
  `ADAPTERS.md` (A-010), `BUGS.md` (B-031), `CHANGELOG.md` (Phase 5 entry incl. the RPE6 rename), `STATUS.md`, evidence
  `evidence/phase5/{m5b_gate,m6_gate,m5_dump}.txt`.
- Gates (`evidence/phase5/m6_gate.txt`): replay OK, golden 373/373, loop 7/7, smoke OK, units 208, BOUNDARIES OK (W1 48 =), API +0/-0/~0,
  AE D4 OK, BAKE OK, TEXT OK, D4 compat OK (baseline_v1 and owner baseline_v0); `ae_ci.py --quick` OK.
- Owner follow-ups: full `python tools/ae_ci.py` on the reference machine; B-024 decision; engine name in window title/splash (not done, owner call);
  `/home/user/uploads/ENGINE_MASTER_PROMPT(2).md` (the upload copy) still carries the RPE5 wording — the in-tree copy is renamed.
- Workspace slimming (sandbox quota): `tools/slim_tree.py --apply` removed the scratch sets `tests/golden/sandbox_linux` (33.9 MB),
  `tests/loop/sandbox_linux` (0.1 MB) and the runtime `assets/voice/_radio_cache` (9.1 MB) → tree 77 MB. The sandbox oracle sets are
  regenerable in ~2 min (`ACA_GOLDEN_SET=sandbox_linux python tools/ae_golden.py capture`, `ACA_LOOP_SET=sandbox_linux python tools/ae_loop.py record`);
  the current tree verified 373/373 and 7/7 against them, so a recapture from this tree is the same reference. Owner sets untouched.
- 2026-10-15 Phase 6 (P6-M0..M6, PARTIAL): engine.render2d queue/kernel + game.render host (A-011); M5 frame peeled from 28 custom
  draws to 1 (`m5.player`, B-033) with golden 373/373 after every step; camera math and the multiplicative light map moved into the
  engine; `ae_d6_gate.py` + CI row ratchet custom draws (count and names). Full gate green (`evidence/phase6/m3_m5_gate.txt`:
  loop 7/7, replay OK, units 240, smoke OK). Phase does NOT exit: D6 zero-custom blocked on the avatar recording-`Pen` refactor
  (owner call) and the §6.22 budget awaits the reference machine. ADR-017, `reports/phase6.md`, B-032..B-036.
- 2026-10-15 Phase 6 closed: B-033 Pen sink (`engine.render2d.pen`) through player/weapon_rig/adornments -> M5 custom draws 0
  (`ae_d6_gate.py --strict` OK); `tools/ae_bench.py` §6.22 scenario 12.94 -> 9.46 ms avg after the pixel-identical radio-noise
  cache and batched rain; full gate + `ae_ci.py` green (`evidence/phase6/final_gate.txt`, 242 unit tests). Phase 6 DONE in the
  sandbox; owner reference-machine re-run pending. Leftovers: B-034 (peel M1-M4), B-035, B-036 -> Phase 7 candidates.
- 2026-10-15 Phase 7 executed (P7-M0..M6): kernels `engine.level`/`engine.dialogue` + unit tests;
  exporters/checkers `tools/ae_level_export.py`, `tools/ae_level_check.py`,
  `tools/ae_dialogue_export.py`, `tools/ae_dialogue_check.py`; game access `src/game/levels.py`,
  `src/game/dialogues.py`; content `src/game/content/levels/*.level.json` (13),
  `src/game/content/dialogue/*.dlg.json` (2). Flipped: m1/map.py, m2/world.py, m3/maps.py (x5),
  m4/maps.py (x2) + m4/flow.py liaison, m5/maps.py (x4) + m5/flow.py Maru. CI rows `level`/`dialogue`
  added, `data validation` TODO retired; API snapshot re-recorded (66 modules, 451 names);
  ADR-018; `reports/phase7.md`. Sandbox oracle sets recaptured at phase start, deleted at close.
- 2026-10-15 Phase 8 executed (P8-M0..M6): kernels `engine.timeline`, `engine.render3d` + 8 unit tests;
  tools `ae_timeline_export/check`, `ae_set3d_check`, `ae_timeline_edit`; game access
  `src/game/timelines.py`, `src/game/render3d_bridge.py`; content `timelines/*.timeline.json` (22),
  `sets/m5.vasile_office.set3d.json` (1). Flipped: 20 `*_shots` definitions (cutscenes/engine.py,
  missions m2/m3/m4/m5 meta.py), `missions/m4/flow.py` ladders, `cutscenes/m5mid3d._office_set`.
  `engine/scene/cutscene.py` gained `from_timeline`. CI rows `timeline`/`set3d` added; API snapshot
  re-recorded (72 modules, 491 names); ADR-019; ADAPTERS A-012; `reports/phase8.md`. B-037 fixed
  (test clock pin in `tests/unit/test_render_adapters.py`). Sandbox oracles recaptured at phase
  start, deleted at close.

## 2026-10-16 (Arena sandbox) - RPE6 Phase 9 closed (sandbox)
- P9-M3 adoption finished: settings schema/store/live consumers + UI
  (COMFORT flash/shake, GAMEPLAY text speed); breach white-out capped via
  per-source scaling + soft luminance ceiling in m5fx3d.cap_flash.
  Fixed: camera shake magnitude must stay int for randint; the cutscene
  exec-harnesses (unit test + smoke) seed `_text_speed_interval`.
- P9-M4: `src/game/save_adapter.py` (ae.save/1 capture/restore: STATE via
  dir(), player, enemy components+legacy attrs with components-first
  order, object-list rebuild only when fully plain, mission module
  globals incl. $set/$tuple tagging, RNG states; no aliasing, no class-
  default materialisation); M5 checkpoint starters snapshot alongside the
  legacy save. `tools/ae_replay_check.py` AE REPLAY-CHECK: OK (5/5) -
  key lessons: capture after a 30-frame warm-up (lazy first-frame init
  burns ~6450 LEGACY draws); restore-side aliasing of snapshot lists.
- P9-M5: `src/game/input_adapter.py` + snapshot remap in
  `app._legacy_frame`, bindings in settings["bindings"], live CONTROLS
  binding tab (was "not available"). Gamepad folds into the forced set.
- P9-M6: CI rows replaycheck+flash; ADR-020; reports/phase9.md; API
  79/535 (re-recorded at M1/M2); units 271 OK; golden 373/373; loop 7/7;
  replay OK; smoke OK. Phase 9 EXITED (sandbox); owner ae_ci.py rerun pending.

## 2026-10-16 — RPE6 Phase 10 M3 (Mission 0, D2 proof) GATED
- `tools/ae_new_mission.py` scaffolder + `docs/engine/tutorial_add_mission.md`;
  generated Mission 0 (m0): level/dialogue/timeline/set3d data + thin host
  over Enemy/Player + engine.ui widgets; wiring in game_core/app/dev_jumps.
- `tools/ae_mission0_check.py`: AE MISSION0 OK — engine tree sha unchanged
  (82 files, e26ff0bd...), scripted playthrough completes, outro renders.
- W1 baseline 48 -> 49: the one deliberate core.game_core -> missions.m0
  edge every mission has (not a regression; ADR-021 to record).
- Gate: compileall OK, boundaries OK, text OK, smoke OK, units 276 OK,
  golden OK. CI TODO row "mission 0" retired (live row added).

## 2026-10-16 — RPE6 Phase 10 M4 built (validate/bench-budget/engine3d-parity/package)
- `tools/ae_validate.py`: AE VALIDATE OK (49 content files via public loaders).
- Bench budgets: `tools/bench_budgets.json` (owner 10 ms per §6.22; sandbox
  caps avg<=17/p99<=24 recorded 2026-10-16) + `ae_bench.py --check-budget`.
- `tools/ae_engine3d_parity.py`: software-backend determinism OK (M2 film +
  m0 set); GL diff stays owner-run `tools/engine3d_check.py`.
- `tools/ae_package.py`: built RPE6-0.1.0.zip (1076 files, 34.8 MB) +
  manifest; --check OK. dist/ deleted after evidence (build on demand).

## 2026-10-16 — RPE6 Phase 10 M4+M5+M6 GATED (phase complete in sandbox)
- M4: ae_validate OK (49 files); bench budget row OK vs sandbox caps;
  engine3d parity OK (software determinism; GL owner-deferred);
  ae_package built+checked (zip deleted after evidence).
- M5: ARCHITECTURE.md + 14 new subsystem pages (16 total); gauntlet
  CLEAN (92 shots x2 fresh offsets, 5 gameplay segments x30 shifted).
- M6: ADR-021 written; first full CI caught a real D4 hard hit in
  devtools (`hasattr(v, "__dict__")`) — fixed in code, not exempted;
  re-run: AE CI: OK (implemented gates), 26/26 rows, 0 TODO rows.
  Evidence: docs/engine/evidence/phase10/final_gate.txt + gauntlet.txt.
- Phase report: docs/engine/reports/phase10.md (D1-D12 table;
  B-038 surfaced; D12/GL/baseline_v0 = owner-machine runs).

## 2026-10-16 — RPE6 Phase 11 steps 1-4 (3D visual upgrades) 
- Step 1 presets: engine/render3d/presets.py + content/lighting3d (6 files);
  sets use "lighting"; bridge.set_lighting blend; test_presets 5 OK.
- Step 2 local lights: engine3d set_lights (software per-face + GL shader),
  scene3d point/spot nodes + attach_light; depot/office data lit.
- Step 3 blob shadows: renderer discs (clamped + bounded cache after an
  OOM kill in the parity run), bridge.shadow_prims, humanoid contacts.
- Step 4 baked AO: bridge _annotate_ao/_apply_ao + seg tessellation;
  side effect: office GUARD banner painter occlusion fixed.
- quality_3d setting (settings_store/user_settings); ae_bench3d + budgets
  + CI row; proof sheets previews/upgrades3d/step1..4 + final_sheet.png;
  golden sandbox set deliberately re-captured (373); gauntlet clean;
  API snapshot 80 modules/547 names; M0 engine hash re-frozen 57dc9dd9
  (justified, phase11 report); B-039 logged+fixed. ADR-022 written.
- P11 steps 5-11 (2026-10-16, sandbox): post-FX (post3d + grades +
  shot "post" data), weather (weather3d, yard set; W1 fix: FX injected
  by host, not imported), ADR-023 baked cast shadows (fingerprint-
  cached), character polish (rig EXPRESSIONS/set_expression/solve_look,
  dialogue-driven mouth 50ms/char), textures (ae.texture/1 palettes,
  software nearest rasterizer w/ stride path; seg cap 0.85 on textured
  prims), animated props (t expressions in set fields, flicker bulbs,
  depot TV), ADR-024 mesh import (glTF/OBJ -> ae.mesh/1, barrel).
  Low-end: render scale per quality tier + per-tier bench rows.
  Gates: AE CI OK (evidence/phase11/final_gate_steps5-11.txt),
  gauntlet clean (93x2, 5x30), units 312, golden recaptured per step,
  engine pin re-frozen per step -> 7069c19d (83 files).

## 2026-10-16 — Engine boot bumper (RPE6)

- New `_EngineIntroState` in `src/app.py`, chained `BOOT_INTRO -> ENGINE_INTRO -> MENU`:
  after the Retardovici Inc. studio ident, a 216-frame (3.6 s) engine bumper plays —
  a gold ECG "pulse" trace sweeps a dark scope grid, heartbeat sting at t=62, then
  the wordmark "POWERED BY / Retardovici PULSE ENGINE / 6 GOLD" with `RPE6 // ENGINE IDENT`
  corner label. Skippable (Space/Enter/Esc/click), same pattern as the studio bumper.
- Strings via the table (`app.powered_by`, `app.engine_name`, `app.engine_gold`,
  `app.engine_ident` in `src/game/content/strings/en.json`); all procedural drawing,
  no new assets. Cursor hidden during the bumper, restored by the menu states.
- Gates: compileall OK; `tools/smoke_test.py` **SMOKE TEST: OK** (string-table +
  glyph rows included); boot-crash unit 6 OK; live dummy-driver run captured the
  sweep, the wordmark, and the menu landing — `previews/boot_intro_sheet.png`.

## 2026-10-16 — GL blob-shadow crash fix (M5 finale) + finale lightning pass

- **Crash (owner, Windows/GL):** `GLRenderer` never overrode
  `add_blob_shadow`, so every humanoid queued a software-format
  `(key, callable, args)` item that `_composite` read as a line and
  unpacked a float as screen points (`TypeError` in the M5 finale).
  Fix: `core.py` factors the blob maths into `_blob_item()` (software
  append byte-identical); `gl.py` queues blobs as GL `"sprite"` items
  (layer 1) and `_composite` draws any leaked callable item instead of
  crashing, skipping degenerate lines. New `tests/unit/test_gl_composite.py`
  (6 tests, context-free) pins all three paths. GL proof on real GPU
  still owner-side, like the rest of the GL backend.
- **Finale, better:** scripted lightning in `m5shadow3d.py` — strikes at
  4300 / 26850 / 33800 ms lift fog (sky follows), cool the frame light,
  and veil the frame; thunder rumbles ~0.75 s later (new procedural
  `_gen_thunder_rumble`, `m5_thunder` foley). Flash honours
  `flash_reduction` (0.35). Gentle fade-in (96 alpha) and fade-out to
  black over the last 2 s. All pure functions of the authored clock:
  deterministic-seek check still pixel-exact.
- Gates: compileall OK; `m5_shadow_check` OK; units 318 OK; smoke OK;
  boundaries OK (W1 49 =); golden 373/373 (sandbox set recaptured, then
  slimmed back out). Proof: `previews/finale/before_after.png`.

## 2026-10-16 — Finale walk rework + background leak fixes

- **Walk (the "weird" gait):** `gait()` in `m5shadow3d.py` ran with
  STANCE=0.25 — each foot grounded 25% of the cycle, so both feet were
  airborne half the time (a bouncing run cycle at walk speed), with
  13 cm marching foot-lift and 63 mm pelvis bounce. Now STANCE=0.56
  (~12% double support, no flight phase), toe clearance ~5 cm, pelvis
  yaw 3.0->2.2 deg, Maru stride target 1.2->1.35 m (cadence 2.15 steps/s
  at her 1.45 m/s), Ucilev UC_STRIDE .64->.78. Probe: stance drift
  33->7 mm, swing clearance 133->82 mm, Ucilev pelvis bob 19 mm; the
  check's planted-foot assertions still pass exactly.
- **Background leaks:** the designed skyline spanned only x -20..17, so
  roof/discovery/escape framings ran off its edges into empty haze.
  Seven more masses (x -39..45, appended last so existing RNG draws are
  unchanged). The stairwell mouth was a black slot: warm lamp panel on
  the interior back wall + threshold spill now glow through the door,
  and the bulkhead front got a vent/conduit so close-ups are not bare
  planes. World shell/seal untouched.
- Gates: compileall OK; m5_shadow_check OK (median render 55.2 ms);
  units 318 OK; smoke OK; boundaries OK (W1 49 =).
  Proofs in `previews/finale/` (walk_maru, walk_ucilev, leak_sheet).
