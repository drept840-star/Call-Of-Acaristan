# Subsystem: `engine.dialogue` (Phase 7)

Branching dialogue as data: files under `src/game/content/dialogue/`.

```
engine.dialogue
  model.py           Dialogue (id, start, speakers, nodes), from_dict/load_dialogue/validate
  runner.py          DialogueRunner(dialogue, host) over the DialogueHost protocol:
                     flag(name), var(name), set_var(name, value), emit(name, payload),
                     resolve(node) -> next node id, speaker_meta(speaker) -> dict
src/game/dialogues.py  facade: dialogue(id) with per-id cache
```

Conditions inside nodes are strings — `flag("x")` or `var("n") OP
number` — evaluated by the runner's evaluator; unknown shapes raise
rather than silently passing. `begin()` / `advance()` / `choose(i)`
drive the walk; hosts render the current `DialogueLine` (Mission 0
uses the legacy `cutscenes.draw_dialogue_box` so the look matches the
campaign). Authoring errors surface via `tools/ae_validate.py`.
