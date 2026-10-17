# ADR-002: ECS-lite — dataclass components in per-type dicts, adapters over legacy objects
Status: proposed
Date: 2026-10-11
Context: Legacy objects are ad hoc: 32 `getattr(x, "_private", default)` sites, and `STATE` carries 478 fields, 275 of them mission-named (AUDIT §4, §8). CPython can't exploit an archetype ECS's cache layout. The needs are clarity, serialisation (D8) and tooling (D9).
Decision: Implement §6.4 as written. `@component` dataclasses are registered with a version. `World` stores `dict[type, dict[EntityId, comp]]`, `query()` iterates the smallest store, and despawn is deferred to `POST`. Systems declare reads and writes and run in phases PRE/SIM/POST/RENDER_SUBMIT; debug asserts that render systems never write. Prefabs are JSON with `extends`. Migration goes through `EntityAdapter` views over `Enemy`/`Player`, one system at a time, each adapter listed in ADAPTERS.md.
Alternatives considered: archetype/numpy SoA (deferred until `ae_bench` demands it); typed class inheritance (no generic serialisation or inspection, and stuffing keeps returning).
Consequences: Some per-query Python overhead, budgeted in Phase 5. The component schema becomes the backbone of the save format (ADR-010).
Verification: `ae_dump_components.py` works on a live M5 stage; replay hashes for m1–m5 stay identical during migration; the grep gate shows 0 underscore getattr/setattr on entities.
