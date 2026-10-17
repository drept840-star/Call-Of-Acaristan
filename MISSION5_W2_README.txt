Mission 5 "Martial Law" - patch W2 (world + flow)
Install: unzip into the project root (same folder as acaristan.py) AFTER W1, overwrite.
Adds:    src/missions/m5/world.py, src/missions/m5/flow.py
Changes: src/missions/m5/__init__.py (facade re-exports), tools/smoke_test.py
         (check_mission5_start, check_mission5_stage_ladder,
         check_mission5_checkpoints_and_maru_fail), docs/MISSION5_BUILD_PLAN.md,
         RESUME_PROMPT.txt (points at W3).
Verify:  python -m compileall -q src tools ; python tools/smoke_test.py  -> SMOKE TEST: OK
Not yet playable: no systems/draw (W3) and no game_core/app routing (W4).
