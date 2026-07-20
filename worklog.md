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
- player.resolve_melee(player, enemies, solid_walls, blood_color): unified melee resolver with range 52, ±60° cone, wall-LOS check, damage 78, 10 particles, shake 8. Replaces M1's inline block (range 48, dmg 80, 8 particles) and M2's inline block (range 55, no cone, no LOS, dmg 75, 12 particles).
- ui_hud.draw_objective_panel(surface, text, x, y): unified objective banner (520 px wide, "OBJECTIVE:" prefix prepended). Replaces M1's 450 px inline panel and M2's 620 px inline panel.
- ui_hud.draw_pinned_radio(surface, pinned_texts, x): unified pinned-radio renderer at bottom-left, capped to last 4 messages. Replaces M1's "all messages bottom-left" and M2's "last 2 top-right".

State changes:
- state.py: added STATE.camera_initialized flag (set False on init, set True by camera.update_camera on first frame).
- mission.py: added MAP_W/MAP_H constants derived from mission1_map (30 cols × 24 rows).
- mission.py start_mission: resets STATE.camera_initialized = False and STATE.cam_kick_x/y = 0.0 on every mission (re)start.
- mission2.py start_mission2: sets STATE.camera_initialized = True after _snap_camera_to (since the camera is pre-snapped).
- mission2.py: STATE.show_minimap changed from False to True (was a bug — players thought the minimap was broken).

Ported call sites in mission.py:
- Camera update at ~917-927 → camera.update_camera() with map_w=MAP_W, map_h=MAP_H.
- Melee block at ~950-993 → player.resolve_melee() (also added STATE.melee_hit_done = False reset at swing end, which M1 was missing).
- Bullet/wall collision at ~1000-1016 → camera.collide_bullet_walls() + effects.burst() + effects.play_impact().
- Bullet/volkov + bullet/commander + bullet/enemy particle loops → effects.burst().
- Bullet/player-hit shake → effects.shake(6) (was direct assignment).
- Player death feedback at ~884-893 → effects.shake(22) + effects.burst(48, speed_mul=1.6) (was 50 raw Particle(), no shake).
- Enemy death burst at ~1075 → effects.burst(24) (was 25 raw Particle()).
- Bullet render at ~1886-1896 → camera.draw_bullets(with_glow=True).
- Objective panel at ~2399-2404 → ui_hud.draw_objective_panel() (and removed "OBJECTIVE:" prefix from text variables).
- Pinned radio at ~2255-2275 → ui_hud.draw_pinned_radio().
- Direct shake assignments at lines 498 (death seq, was =20) and 575 (breach bang, was =28) → effects.shake(20) and effects.shake(28).

Ported call sites in mission2.py:
- _update_camera at ~3913-3976 → delegates to camera.update_camera() with per-stage focus_factor or factor_fn (smoothstep for sniper stage, 0.38 for focus pulls, 0.14 default). Preserves mission2_camera_snap and mission2_camera_focus cutscene features.
- Local _burst() function at 782-788 → replaced with _burst = effects.burst alias (24 existing call sites unchanged).
- Melee block at 3348-3362 → player.resolve_melee() (also added STATE.melee_hit_done = True on hit, which M2 was setting inside the loop — now set after the resolver returns the hit enemy).
- Bullet/wall collision at 3529-3534 → camera.collide_bullet_walls() + effects.play_impact() (was flat audio.play(); now 3D positional).
- Bullet/enemy hit at 3570-3571 → effects.play_impact() (was flat).
- Bullet/player-hit shake at 3578 → effects.shake(6) (was max() inline).
- Bullet render at 8273-8275 → camera.draw_bullets(with_glow=True) (was missing glow halo).
- Objective panel at 7042-7047 → ui_hud.draw_objective_panel().
- _draw_radio_text at 7413-7426 → ui_hud.draw_pinned_radio().
- Player death shake at 3987 → effects.shake(22) (was direct assignment).
- Tanker blast shake at 2699 → effects.shake(160) (was direct assignment).

Verification:
- All 8 modified files pass py_compile (effects, camera, player, ui_hud, state, mission, mission2, weapons).
- All imports succeed: config, state, effects, camera, player, ui_hud, weapons, mission, mission2.
- smoke_test.py: 17 of 18 checks pass. The single FAIL is draw_settings (pre-existing bug — smoke_test passes 7 args to a function that requires 20; unrelated to this refactor).
- Integration tests pass:
  - effects.shake max-clamps correctly (5 then 3 → still 5; 10 → 10).
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
