MISSION 5 - W3 PATCH (systems + draw)
Overlay into the project root (after W1, W2). Root-relative paths.

NEW
  src/missions/m5/systems.py  game_update(keys) ported from m4 (enemy bullets
                              hit Maru before the player; deaths call
                              world._register_guard_kill + hostiles_killed)
  src/missions/m5/draw.py     game_draw(cam_x, cam_y): M4 tile art via
                              artpack, procedural H/S/W/G, Guard troopers in
                              black + red armband, Maru + HP bar, dialogue
                              panel, raid timer, objective beacon, HUD
CHANGED
  src/missions/m5/__init__.py facade loads systems + draw
  src/core/state.py           m5_mag_drops / m5_bandage_drops reset
  tools/smoke_test.py         check_mission5_update_and_draw
  docs/MISSION5_BUILD_PLAN.md W3 ticked
  RESUME_PROMPT.txt           points at W4
Gate: compileall OK, SMOKE TEST: OK (incl. mission5_update_and_draw).
