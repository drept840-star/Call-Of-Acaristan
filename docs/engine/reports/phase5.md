# Phase 5 report — World/ECS-lite and standard systems
Date: 2026-10-15   Commits: n/a (no git in the sandbox; changed-files log in `docs/worklog.md`, entries "Phase 5 P5-M1" … "P5-M6")
Environment: Arena Linux sandbox, Python 3.12, pygame-ce 2.5.8 (owner reference machine: 2.5.7). Golden/loop oracles ran against the sandbox sets (`ACA_GOLDEN_SET=sandbox_linux`, `ACA_LOOP_SET=sandbox_linux`, captured from the owner's Phase-4-exit tree before any Phase 5 edit); replay ran against the owner's `baseline_v0` (through the compat proof) and the re-recorded `baseline_v1`.

## Outcome (first line = honest status)
DONE for the §7 exit criteria (D4 holds, replay parity for every mission segment through the adapters, component dump tool works) — **PARTIAL for the §7 work list**: movement, collision, combat, AI, interaction, pickups and props are *hosted* under the scheduler (legacy update = declared SIM system) and every object they touch is an entity with declared components, but their logic was **not** rewritten into standard systems (deliberate, ADR-016 §4–6). The owner must re-run the full gate on the reference machine before accepting (the 8 known cross-machine golden ids, CHANGELOG Phase 4 pre-flight).

## Exit criteria
- [x] D4 holds — entities with declared components, no getattr-default attribute stuffing on shared types — evidence: `tools/ae_d4_gate.py` → `AE D4: OK (hard=0, remaining mission-prefixed sites=0, exit criterion met)` (`evidence/phase5/m6_gate.txt`); `ae_dump_components.py --seg m5` lists `M5Guard` on all 7 guards (`evidence/phase5/m5_dump.txt`).
- [x] Replay parity for every mission segment, translated through the adapters — evidence: `tools/ae_d4_replay_compat.py --set baseline_v0` → `AE D4 REPLAY COMPAT: OK` (150/150 snapshots, owner's pre-migration baseline; `evidence/phase5/{m4,m5,m5b}_replay_compat.txt`); `tools/ae_replay.py check` → `AE REPLAY: OK` on `baseline_v1` (5 segments, snapshot v2 hashes components + doors).
- [x] Component dump tool works for a running M5 stage — evidence: `evidence/phase5/m5_dump.txt` (Lower Quarter after 180 steps: 8 entities, 8 component types, systems `PRE legacy_roster` / `SIM legacy_mission_update`); M3 dump in `evidence/phase5/m5b_gate.txt` (22 entities incl. 13 `M3Door`).
- [x] Grep gate (no `setattr`/`getattr` with underscore-prefixed or mission-prefixed attributes on entity objects in game code) — evidence: `ae_d4_gate.py` wired into `tools/ae_ci.py` (row "entity components (D4 grep gate)").
- [x] Standard oracles green after every milestone — evidence: `evidence/phase5/m6_gate.txt`: replay OK, golden 373/373, loop 7/7, smoke OK, units 208, BOUNDARIES OK (0 engine violations; W1 48 = baseline), API +0/−0/~0, BAKE OK, TEXT OK.
- [ ] Work-list items "migrate movement, collision, combat, AI hosting, interaction, NPCs, pickups, props" — gap: hosted (`LegacyMissionSystem`) and entity-backed, logic still inside the five mission `game_update`s; plan: split per family when the draw paths become RENDER_SUBMIT systems (Phase 6) and placements/role tuning move to level data (Phase 7) — see ADR-016 §6.

## What shipped (work list)
- `src/engine/world/` kernel (P5-M2): `_component.py` (`@component`, versions, `from_dict/to_dict`), `entity.py` (`World`: per-type dicts keyed by `EntityId`, queries in insertion order, deferred despawn flush, read-only guard), `system.py` (`System`, `FunctionSystem`, `Scheduler` PRE/SIM/POST/RENDER_SUBMIT with `describe()`), `std.py` (`Transform, Velocity, Health, Collider, Faction, AIBrain, Lifetime, Label, Tags, WalkCycle, HitFlash, LegacyRef`), `prefab.py` (`PrefabLibrary` with `extends`, `diff`, `instantiate`, `load_prefabs`). Engine never imports game code (BOUNDARIES 0).
- `src/game/world/` bridge (P5-M3, A-010): `LegacyRoster` mirrors `STATE.enemies/player/pickups/corpses/fire_zones/npcs/doors` as entities with **view** components over the legacy fields; `install/step/ensure/get/entity_of/reset`; selective reset on list rebinding (B-030).
- D4 codemods (P5-M4/M5/M5b): `M5Guard` (37 sites), `M3Guard` + `Label` (57), `M4Guard` + `Label` (8), `M2Role` (11), `M3Door` (38), `arena_view._PoseMeta` (6 attrs on `Player`), `Tags({"removed"})`; shared `Enemy`/`Player` keep class-attribute defaults only. Mission components live beside the mission (`missions/mN/components.py`).
- Hosting (P5-M6): `game.world.step(fn)` runs the mission dispatcher as the declared SIM system `legacy_mission_update` (order 0) between the PRE roster sync and the POST flush; `core.game_core.game_update` no longer hand-sequences phases.
- Tools: `tools/ae_dump_components.py` (`--seg`, `--seconds`, JSON), `tools/ae_d4_gate.py` (hard rule + ratchet baseline `evidence/phase5/d4_baseline.json`), `tools/ae_d4_replay_compat.py` (old-name re-injection proof), `tools/ae_replay.py` snapshot v2 (`~world`: components + doors), sandbox-selectable golden/loop sets (P5-M1), `tools/ae_ci.py` rows "entity components (D4 grep gate)" and "component dump (running M5 stage)".
- Tests: `tests/unit/test_engine_world.py` (kernel), `tests/unit/test_game_world_bridge.py` (ensure/get semantics, selective reset, removed tag, door survives an enemy-list swap, hosted step order + exception path): 208 unit tests total.

## Metrics
- Boundary violations: 0 engine → 0 engine; W1 shared→mission edges 48 → 48 (baseline held; `ko_playability_audit.py` routes through `_sweep_mod`).
- STATE fields: +0 (no new `STATE` fields; banned §10).
- D4: 32 `getattr(_private, default)` sites (Phase 0 audit) → **0** hard sites; mission-prefixed stuffing sites 76 (first ratchet after M5) → **0**; ~157 call sites codemodded to `ensure()` helpers.
- Procedural draw calls (census): unchanged this phase (Phase 6 scope).
- Duplicated UI functions: unchanged this phase.
- Adapters: added A-010 (legacy world roster + hosted SIM); removed 0; open A-001…A-010.
- Bench: not re-run (no budget gate until Phase 10); loop oracle 7/7 segments identical in 43 s, replay 5/5 — the `ensure()` indirection is below the oracles' noise.
- Unit tests: 187 → 208. Golden 373/373, loop 7/7.

## Visual evidence
- Golden comparisons: 373, failures 0 (sandbox set); against the owner's `baseline_v0` the same 8 known cross-machine ids differ (SysFont rasterisation; CHANGELOG "Phase 4 pre-flight"), none new.
- Images reviewed: `tests/golden/_verify/sandbox_linux/*.now.png` during P5-M5 (m3 cells) — no differences; nothing to attach.

## Risks & caveats
- Reference machine not yet run: the owner must execute `python tools/ae_ci.py` (full) and `python tools/ae_d4_replay_compat.py --set baseline_v0`; `baseline_v1` was re-recorded in the sandbox after the compat proof (deliberate, logged — not a silent re-baseline).
- The replay oracle hashes `Enemy/Player/Door.__dict__` (B-029): future field moves must repeat the compat-proof-then-re-record discipline.
- `WalkCycle` is advanced from the draw path by design (ADR-016 §5); a harness that renders without drawing will show `primed=false`.
- `LifetimeSystem`/`HitFlashSystem` intentionally not enabled (double-decrement risk, ADR-016 §6).
- B-024 (m5 baked-art drift between machines) still open — owner decision.
- `src/ui/arena_view.py` `_PoseMeta`: behaviour-identical by inspection + smoke mirrors (`arena_sprite_rig_and_anim`, `mp_host_and_portmap`, `arena_look_reaches_the_sprite`); the arena has no replay/golden oracle — flagged in BUGS (B-031).

## Decisions (ADRs)
- ADR-002 ECS-lite (unchanged); **ADR-016 legacy world bridge** (view components, mission components beside missions, compat-proof-then-re-record, hosted SIM, render-driven WalkCycle, Lifetime/HitFlash deferred, prefabs deferred to Phase 7).

## Next phase entry check (Phase 6 — Render2D queue, camera, static layers, lighting, post-FX)
- Entry: Phase 5 gates green on the reference machine; `engine.render2d` + `engine.lighting` kernels already exist from Phase 1/2 (`core/render_util.py`, `core/lighting.py` shims A-006).
- First steps: (1) draw census per mission (`audit/draw_census.md`) → pick M5 gameplay draw path as the first RENDER_SUBMIT system (`GuardRenderSystem` per §6.4 step 2, consuming `Transform/WalkCycle/M5Guard`); (2) golden harness renders through the queue so `WalkCycle` can move to POST (ADR-016 §5); (3) static-layer bake from level decor behind the existing `ae_bake.py` hashes.
