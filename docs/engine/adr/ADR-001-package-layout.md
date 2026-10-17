# ADR-001: Package layout — `src/engine/` plus keeping `missions/` (no `game/` move yet)
Status: proposed
Date: 2026-10-11
Context: §5.2 allows `src/game/` or keeping `missions/`. The audit shows 50 mission files and 61k lines under `missions/`, plus per-mission take modules under `cutscenes/` and `art/`. There are 169 shared → mission import edges, ~120 of them from the `cutscenes/__init__.py` facade and the `cutscenes/engine.py` dispatcher. AGENTS.md documents facade import-order rules, PEP 562 live views and owner-module mutable state. A bulk move would touch every import, break those rules wholesale and produce a non-bisectable diff, against R3.
Decision:
- New engine code lives in `src/engine/<pkg>/` as in §5.2, each package with an explicit `__all__`.
- Game code stays put (`missions/`, `cutscenes/m*`, `art/m*`). "Game" means everything outside `src/engine/` and `src/engine3d/`. The boundary lint classifies modules by path using the rule from `tools/ae_audit.py` (`MISSION_RE`). `app.py` is the allow-listed composition root.
- New data content goes in `content/<mission>/{levels,timelines,dialogue,prefabs,strings}/` at the repo root.
- Engine-like shared modules (`core/render_util`, `core/lighting`, `core/artpack`, `entities/sprite_lib`, `core/fixedstep`, `core/mapbuilder`) move under `engine/` in Phase 2. Re-export shims stay at the old paths and are listed in ADAPTERS.md.
- `engine3d/` is a vendored backend that only `engine.render3d` imports.
- `src/tools/*` counts as TOOLS. The engine never imports it.
Alternatives considered: move everything to `src/game/` now (big bang, no parity benefit); put `engine` at the repo root (`acaristan.py` adds only `src/` to the path).
Consequences: Import paths stay stable. A later `game/` rename remains a mechanical, separate change.
Verification: `check_boundaries.py` shows 0 engine → game edges; smoke, golden and replay stay identical across every move.
