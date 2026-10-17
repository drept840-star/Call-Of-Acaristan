# Subsystem: `engine.anim` (Phase 4–5)

Character figure rendering shared by every mission's cast.

```
engine.anim
  figure_kit.py      draw_character + SPECS per uniform family (KRAP_BLUE, KRAP_UNIFORM),
                     REF_H/HEIGHT proportions, face/mix/dark/lite shading helpers, Pen protocol
  pose_cache.py      PoseCache + POSES/POSE_CAP - baked pose surfaces, capped LRU
src/game/art/        per-mission palettes and the cast painters built on the kit
```

The kit owns the *figure grammar* (proportions, uniform construction,
shading); missions keep identity (faces, palettes, signature gear).
Poses bake once and cache — sprite pipeline changes must regenerate
and commit the packs (`tools/ae_bake.py`), and humanoid vs vehicle
vs prop painters stay separate modules.
