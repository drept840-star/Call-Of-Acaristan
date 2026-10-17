Mission 5 - W7 (3D cutscenes)

Overlay these files onto the project root.

Changed/added:
  src/cutscenes/m5martial3d.py (new)
  src/cutscenes/engine.py
  src/cutscenes/__init__.py (docstring only)
  tools/smoke_test.py
  docs/MISSION5_BUILD_PLAN.md
  RESUME_PROMPT.txt

All 8 Mission 5 cutscenes now render in 3D (software renderer), incl. a
scope POV with a crosshair.
Set ACARISTAN_CUTSCENE3D=0 to force the original 2D scenes.
Gate: python -m compileall -q src tools && python tools/smoke_test.py
