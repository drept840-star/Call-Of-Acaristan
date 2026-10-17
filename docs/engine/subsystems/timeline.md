# Subsystem: `engine.timeline` (Phase 8)

Cutscene and timed-event data: `ae.timeline/1` files under
`src/game/content/timelines/` (23 timelines).

```
engine.timeline
  model.py           Timeline (shots + event tracks), from_dict/load_timeline/validate
  expr.py            the keyframe expression language: check_expr/evaluate;
                     expressions resolve at the key's own time
  player.py          TimelinePlayer + Sample - walks shots/tracks against a clock
src/game/timelines.py  facade: timeline(id), shots(id, legacy) (fresh dicts - mutation-safe),
                     save_timeline() (canonical indent=1 write; devtools F6 + CLI editor share it)
```

Game-side: `CutsceneScene.from_timeline` builds playable shots;
takes are FX hooks registered per module (A-012), so behaviour stays
code and data stays data. Editing: `tools/ae_timeline_edit.py` (CLI)
and the F6 panel in `src/game/devtools.py`; both write through the
same canonical writer, so files never churn style.
