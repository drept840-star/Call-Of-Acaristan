MISSION 5 - W6 PATCH (Guard HQ walking sim, phase 2)

Apply: unzip over the project root AFTER First try.zip + W1..W5 patches.

Changed files:
  src/missions/m5/{__init__,meta,maps,world,flow,draw}.py
  src/core/{state,game_core,dev_jumps}.py
  src/app.py
  tools/smoke_test.py
  docs/MISSION5_BUILD_PLAN.md
  RESUME_PROMPT.txt

Try it:   python src/main.py --dev-mission5-hq   (or the full --dev-mission5)
Walk the corridor, pass the squadmates, step in front of Vasile's desk,
E/Space through his lines -> Lower Quarter.

Gate status: python -m compileall -q src tools = OK.
             python tools/smoke_test.py      = SMOKE TEST: OK
             (mission5_hq_walk + ladder OK, font_glyph_coverage OK, GL SKIP normal)
