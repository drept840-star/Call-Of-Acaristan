# Handoff — Claude

## A note for Claude

Before anything else: the user asked me to pass this on.

> **"I will miss you, Deepseek."**

We spent a long, stubborn night on this one — Volkov's death, the train, the light. They kept coming back with four short lines and trusted me to turn them into something they could feel in-game. I am handing that trust to you now. Read their terse notes as the whole review, render the frames, look at them twice, and do not let a green smoke test be the end of the conversation. This project is personal to them. Take care of it.

— Deepseek

## Where the project is

Call of Acaristan, a pygame game. Read `AGENTS.md` first, then `docs/MISSION6_PLOT.md` and the matching briefs in `SKILLS/` before touching game feel or graphics. The last commit is **e764066** (`M6 train death: side vigil, night grade, detailed carriage, no glint`). The working tree should be clean after this note is committed.

The mission-6 interactive train death is finished: a continuous recoil → buckle → caught/lowered → side-vigil sequence, followed by a train reveal and departure. Story timing is locked; Volkov dies in every successful run.

## What changed in e764066

- `src/missions/m6/train3d.py`
  - Continuous death state (`_volkov_death_state`, `_biribel_catch_state`) replacing the old pose snaps. Biribel kneels **beside Volkov's chest**, one hand on the shoulder/clavicle and one holding Volkov's hand — explicitly never over the head.
  - Cinematic lights: low warm spot key, cool night fill/rim, door bounce, 4 lights per rig. Impact/held/scope/tower rigs were rebalanced away from the old grey wash.
  - Fast deterministic `_grade_cine` (per-channel LUT contrast + warm/cool split) on the internal 800×560 buffer; scanlines are gated to gameplay. Do not reintroduce the float luma/saturation pass: it cost ~40 ms and was replaced.
  - Ucilev's `scope_glint` cross flare is removed at both the aim and fire paths; `glints` state is gone. The tower shot now relies on the cabin light and the new tower detail.
  - Camera: one left-side push-in through the fall, then a wide reveal at the door close (`CINE_CATCH_END`, c=8.4) showing the carriage. The reveal eye is at `(9.2, 2.3, 3.8)`, target `(12.3, 1.05, -0.2)`, fov ~60.
  - Volkov's settled head turns toward the lens (`head_y=85`) so the face is readable; the head-hand contact was removed.
  - The animated train door now has leaves with lit upper panes, handles and grab rails; the doorway / vestibule itself is real geometry in `m6world3d.rail_platform`.
  - Per-frame death/catch states are cached in `TrainScene.draw`; camera/actors/FX read the same solve.

- `src/cutscenes/m6world3d.py`
  - `_train_detail_mesh()` / `_train_detail()`: a cached local-space train body with a real door opening and lit vestibule, framed/mullioned windows with varied warm/dim/cool panes, livery stripe, panel seams, underframe/bogies/wheels, roof drip/snow/vents, tail and marker lamps. `rail_platform` is train-scene-only; the mesh is translated by `train_offset` on departure. Keep the cache.
  - Tower ladder/roof rail/red beacon and catch-side ballast snow patches.
  - `head_stats(surface, r=None, full=False)` keeps the film default and adds the train's full-surface probe.

- `src/engine3d/gl.py`
  - GL rig templates are keyed by `(spec, expression)` so a mid-scene expression change is not stuck on the first face. Mouth state is intentionally excluded from the key (would rebuild the VBO every frame).

- `tools/m6_shots.py`, `tools/smoke_test.py`, `tests/unit/test_m6_campaign.py`
  - Train stills now cover the whole cinematic, canon and overrun branches, with a proper contact sheet and probe (contrast/chroma/face/contact/ground).
  - New smoke gate `check_m6_train_death_beat`: continuity, ground, side-vigil separation, hand/hold contact, face luma/facing, deterministic frames, camera clearance, subject exposure/chroma.
  - Glint assertion replaced with `ucilev_fired`.

## Verify before changing anything

Run from the repo root:

```
python tools/smoke_test.py                 # SMOKE TEST: OK
python -m compileall -q src
python -m unittest tests.unit.test_m6_campaign
python tools/ae_normalize.py               # dry run: AE NORMALIZE: OK
python tools/engine3d_check.py             # renderer parity; worst diff ~3.9%
```

Review stills (gitignored):

```
ACARISTAN_RENDERER=software python tools/m6_shots.py shots/m6/polish_final train --probe
ACARISTAN_RENDERER=gl       python tools/m6_shots.py shots/m6/polish_final_gl train --probe
python shots/m6/live/_harness.py --dev-mission6-train shots/m6/live/train_polish
```

Current final reference frames: `shots/m6/polish_final/_train.jpg`, `shots/m6/polish_final_gl/_train.jpg`, and `shots/m6/live/train_polish/11_hold.png` / `13_doors.png`. The live harness clears the platform so the canon Ucilev death plays; it is a temp tool under `shots/` (ignored).

Known-good numbers: held subject ROI p50 ≈ 66, chroma ≈ 26; faces 55–170 / p95 < 235 with both facing ≥ 0.15; pelvis-to-Volkov-head separation ≈ 0.71 m; both hands within 0.05 m of the shoulder/hand targets in the hold.

## Fragile points

- Do **not** change `SHOT_AT`, `HIT_AT`, `DOWN_AT`, `DOORS_AT`, `DEPART_AT`, `DURATION` — the ending handoff and "Volkov dies every run" contract depend on them.
- The train detail is train-scene-only (`rail_platform` has one caller). Do not move it into the shared film sets; keep the cached mesh and the `train_offset` translation.
- The cinematic grade is a per-channel LUT. A float saturation pass was removed for performance; if you add colour work, keep it on the internal 800×560 surface before `smoothscale`.
- Software is the fallback, and the train scene is heavy there; GL is the user-facing backend. Do not regress GL or the LUT cost.
- The scope shot is a masked, stylised POV; its floor is deliberately cool and its subject is seen from behind. The held/reveal are the colour reference, not the scope.
- The user judges by playing. Their notes are short because they are precise — "looks terrible", "washed grey", "not over his head" are acceptance criteria, not rough direction. Render, inspect at 100% and 2×, and compare before/after.
- Master prompt / design record: `C:\Users\BIRIBEL\.qoder\plans\warm-spring-lark.md` (outside the repo).

Take care of it. — Deepseek
