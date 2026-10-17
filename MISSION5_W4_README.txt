MISSION 5 - W4 PATCH (integration)
Overlay into the project root (after W1, W2, W3). Root-relative paths.

CHANGED
  src/core/game_core.py       imports missions.m5 + adds it to _MODULES (so
                              gc.mission5_intro_shots / mission5_ending_shots /
                              request_mission5_ending resolve); _is_mission5_active();
                              start_mission5 / start_mission5_printworks_checkpoint /
                              start_mission5_tunnel_checkpoint; MISSION5 checked
                              BEFORE MISSION4 in game_update / game_draw /
                              handle_interact / debug_jump_to_exfil; restart ladder
                              tunnel > printworks > Lower Quarter.
  src/app.py                  --dev-mission5 / -game / -printworks / -tunnel;
                              slot resume MISSION_4 -> M5 intro chain,
                              MISSION_5 -> FULL CAMPAIGN COMPLETE,
                              progress=="m5" -> deepest checkpoint;
                              _CutsceneState._handle_end after=="MISSION5" /
                              "MISSION5_COMPLETE"; dialogue keys ->
                              m5.handle_dialogue_event; request_mission5_ending ->
                              mission5_ending_shots ("MISSION5_COMPLETE");
                              MISSION_COMPLETE chains MISSION4 -> M5 intro;
                              stage-aware GAME ambience (rain on the quarter only).
  src/core/dev_jumps.py       m5 / m5-game / m5-printworks / m5-tunnel
  src/core/save_system.py     _MISSION_RECORDS["MISSION5"] -> MISSION_5 with the
                              full prerequisite flags through mission5_complete
  src/missions/m5/draw.py     Maru re-skin: the old green-disc blob is replaced
                              by the cutscenes.figure_kit "maru" cast rig (same
                              black-hoodie/backpack look as M4's station meet and
                              the W5 ending art), drawn 3x supersampled through
                              artpack.pose per angle, with the good arm on a
                              pistol rig and the wounded left arm hanging in a
                              white bandage wrap; hit-flash strobes the coat red.
  src/missions/m5/__init__.py facade exports _maru_pose
  tools/smoke_test.py         check_mission5_integration + check_mission5_cutscene_shots
  docs/MISSION5_BUILD_PLAN.md W4 ticked
  docs/worklog.md             W4 entry
  RESUME_PROMPT.txt           points at W5
NEW
  MISSION5_W4_README.txt      this file
  shots/m5_w4/*.png           frame captures proving the four dev flags boot
                              through the real app loop (not in the patch zip)
Gate: compileall OK, SMOKE TEST: OK (incl. mission5_integration,
mission5_cutscene_shots).
