# Subsystem: `engine.level` (Phase 7)

Level data: `ae.level/1` files under `src/game/content/levels/`
(14 levels).

```
engine.level
  model.py           Level (layers + objects + triggers + paths + lights + decor),
                     from_dict/load_level/to_dict/validate, LevelError
  tiled.py           from_tiled - Tiled JSON import (authoring path), TiledError
src/game/levels.py   facade: level(id), grid(id, legacy_grid) - grid() returns a copy;
                     ACA_LEVEL_SRC=legacy restores the Python tables
```

Runtime contract: missions consume `list[str]` tile grids exactly as
before the migration (engines of record are the mission hosts, not
this kernel); authoring goes through `src/core/mapbuilder.py`, and
the devtools F5 level viewer reads layers/triggers/spawns through
this facade.
