# Subsystem: `engine.world` (Phase 3)

ECS-lite world model: entities are ids, components are typed
dataclass-like records, systems run in declared phases.

```
engine.world
  entity.py          EntityId, component registration, fields_of/schema (save system reads these)
  world.py           World container + WorldError
  system.py          System / FunctionSystem / Scheduler; phases PRE, SIM, POST, RENDER_SUBMIT
  prefab.py          PrefabLibrary (PREFAB_SCHEMA) - data-defined entity templates
  std.py             standard components: Transform, Velocity, Collider, Health, Faction,
                     Tags, Label, Sprite, WalkCycle, HitFlash, AIBrain, Lifetime, LegacyRef
```

The legacy game objects (STATE enemies/player) were never rewritten
onto this wholesale; `LegacyRef` is the bridge, and the Phase 9 save
adapter walks component-shaped `__dict__` data with the same field
introspection (`fields_of`). Mission 0's two enemy types are
prefab-style data (`src/missions/m0/enemy_types.json`) applied to
`Enemy` instances host-side.
