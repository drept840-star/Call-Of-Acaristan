# Subsystem: `engine.scene` (Phase 2)

Scene lifecycle: a stack of `Scene` objects with enter/exit/update/
draw, plus the two specialised scenes the game actually runs on.

```
engine.scene
  scene.py           Scene base
  stack.py           SceneStack (push/pop/replace; summary feeds save snapshots)
  cutscene.py        CutsceneScene - plays a timeline's shots via registered renderers
  inspect.py         InspectScene - the A-007 inspect mirror (INSPECT[key] scenes)
```

Game-side: `src/core/scene_mirror.py` mirrors the stack into the
legacy state machine (app.py is not importable from tests, so the
mirror is the testable seam). Renderers register with
`core.cutscene_registry.register_scene_renderer(id, fn)` where
`fn(surface, t_ms)`; the registry lives game-side because the
renderers do. Phase 9 save snapshots include the scene-stack summary.
