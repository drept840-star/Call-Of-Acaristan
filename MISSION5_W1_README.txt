Mission 5 "Martial Law" - patch W1 (package skeleton)
Install: unzip into the project root (same folder as acaristan.py), overwrite.
Adds:    src/missions/m5/ (meta, maps, facade), docs/MISSION5_BUILD_PLAN.md
Changes: src/core/state.py (M5 fields only), tools/smoke_test.py (check_mission5_maps),
         RESUME_PROMPT.txt (points at W2).
Verify:  python -m compileall -q src tools ; python tools/smoke_test.py  -> SMOKE TEST: OK
Not yet playable: M5 is not routed into the game until milestone W4.
