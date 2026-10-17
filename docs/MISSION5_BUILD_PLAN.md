# Mission 5 "Martial Law" - Build Plan (milestones)

Source of truth for story: `docs/MISSION5_PLOT.md`. Pattern: copy the M4
package contract (`meta -> maps -> world -> flow -> systems -> draw`, re-export
facade, PEP 562 live views, single-owner mutable state).

Every milestone ends with: `python -m compileall -q src tools` +
`python tools/smoke_test.py` (SMOKE TEST: OK) + a patch ZIP of changed files +
RESUME_PROMPT.txt updated to point at the next milestone.

## Stage ladder (`STATE.mission5_stage`)
| Stage const        | Phase | Map            | Gate to next |
|--------------------|-------|----------------|--------------|
| STAGE_HQ           | 2 Guard HQ (walk) | MISSION5_HQ_MAP 30x16 (W6, disarmed walk) | Vasile office dialogue done |
| STAGE_QUARTER      | 3 Lower Quarter   | MISSION5_QUARTER_MAP 40x30 | reach print-works door |
| STAGE_PRINTWORKS   | 4a find Maru      | MISSION5_PRINT_MAP 26x20 | Maru dialogue done -> raid |
| STAGE_RAID         | 4b CQB raid       | same           | raid waves cleared/timer -> basement stair |
| STAGE_TUNNEL       | 5 escort          | MISSION5_TUNNEL_MAP 48x12 | Maru reaches river gate (Maru death = fail) |
| STAGE_DONE         | 6 standoff        | ending cutscene | request_mission5_ending |

Checkpoints (deepest wins): `mission5_printworks_checkpoint_reached`,
`mission5_tunnel_checkpoint_reached`.
Mercy tracking: `STATE.m5_guard_kills` (Lower Quarter kills only).

## Milestones
- [x] P1-P3 Planning (this file).
- [x] W1 Package skeleton: `m5/meta.py` (ids, tiles, stages, shot lists),
      `m5/maps.py` (3 procedural maps, validated + flood-fill connectivity),
      facade `m5/__init__.py`, STATE fields in `core/state.py`,
      smoke check `check_mission5_maps`.
- [x] W2 `m5/world.py` + `m5/flow.py`: world builders, guards, Maru ally
      (follow + HP), stage ladder, dialogue typewriter (Maru + raid),
      checkpoints, fail when Maru dies, `_complete_m5`.
- [x] W3 `m5/systems.py` (game_update, ported from m4) + `m5/draw.py`
      (reuse M4 tile grammar; Guard troopers black + red armband).
- [x] W4 Integration: `core/game_core.py` routing + restart ladder,
      `app.py` intro/ending chains (`MISSION5`, `MISSION5_COMPLETE`), M4
      complete -> M5 intro, `--dev-mission5*` flags, `core/dev_jumps.py`,
      save progress "m5", smoke checks boot/stages/checkpoints/Maru-fail.
- [x] W5 Cutscenes: `cutscenes/m5martial.py` 2D scenes for bulletin,
      safehouse TV, Retardovici TV, river gate/Ucilev; dispatch in engine.
- [x] W6 Guard HQ walking-sim section + Vasile office scene (in m5/; fresh run
  opens at STAGE_HQ; restart ladder tunnel > printworks > quarter > hq;
  --dev-mission5-hq; smoke mission5_hq_walk). Full smoke: OK.
- [x] W7 (optional) 3D versions of the bulletin / standoff via engine3d.
      cutscenes/m5martial3d.py: ALL 8 M5 scenes have 3D takes (incl. a scope
      POV with crosshair/mil dots). engine.py tries 3D first, 2D m5martial is
      the fallback (ACARISTAN_CUTSCENE3D=0 or any 3D error). Smoke:
      mission5_cutscenes_3d.
