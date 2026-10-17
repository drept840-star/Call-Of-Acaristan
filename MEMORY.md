# RULE: Split long tasks into Planning and Writing stages

Applies to: any task too large to finish in a few direct edits (multi-file features, refactors, content generation, long scripts).

## Core rule
Never execute a long task as one undifferentiated blob. Split it into exactly two top-level stages, in order:

1. **Planning stage** — investigate the codebase, pin down requirements, and produce a written plan. No implementation edits during this stage.
2. **Writing stage** — execute the plan as code/content edits, verified against the plan.

Do not start the Writing stage until the Planning stage's plan is written down and agreed.

## Both stages must be further split into milestones
Each stage is decomposed into numbered, independently completable milestones. A milestone is small enough to finish and verify in one work session.

**Planning milestones** (examples):
- P1: Scope + requirements pinned, ambiguous decisions resolved
- P2: Relevant files/modules mapped, constraints and entry points identified
- P3: Final written plan (file list, change order, verification commands)

**Writing milestones** (examples):
- W1: First coherent slice implemented + `SMOKE TEST: OK`
- W2: Next slice implemented + smoke/compile checks pass
- W3: Integration + edge cases + final full verification

## Milestone discipline
- Track milestones explicitly (todo list or a checklist in the plan); mark each COMPLETE only after its verification passes.
- Complete and verify milestones in order; do not jump ahead.
- If a milestone reveals the plan is wrong, pause Writing, fix the plan (re-enter a mini Planning step), then resume.
- Never mark a milestone done on "should work" — run the project gate (`python tools/smoke_test.py`, `python -m compileall -q src`, plus any targeted checks).

## Example
Task: "add a new mission with cutscenes and audio."
- Planning: P1 map M1–M3 patterns and decide structure → P2 list files (mission package, mapbuilder layer, cutscene, audio hooks) → P3 write the plan with change order.
- Writing: W1 map layer + spawns baked and validated → W2 gameplay/update loop + objectives → W3 cutscenes + dialogue → W4 audio hooks → W5 menu/mission-select integration + full smoke test.
