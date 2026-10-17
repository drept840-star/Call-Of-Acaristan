# ADR-003: Data formats — versioned JSON with stdlib validators, optional Tiled import
Status: proposed
Date: 2026-10-11
Context: R8 needs a schema, validator and migration for every format. R10 forbids new dependencies (no jsonschema, no YAML). Levels are `list[str]` grids from `core/mapbuilder.py`, and that runtime type must not change (AGENTS.md).
Decision:
- Content is UTF-8 JSON with LF endings. Tools write sorted keys. Each file starts with `{"schema": "ae.<kind>", "version": N}`. Kinds: level, timeline, set3d, dialogue, prefab, strings, manifest, settings, save, plus the golden.manifest, replay.segment and replay.stream kinds already in use.
- Validators are hand-written stdlib checkers built on a mini type-spec DSL (`engine/core/schema.py`) that reports JSON pointers. Each kind has `migrate(doc)` chained by version.
- `.level.json` stores tile layers as row strings, byte-identical to `MapBuilder.to_strings()`, plus object, trigger and region layers. The loader returns today's `list[str]`.
- Tiled `.tmj` import is dev-only (ADR-008). TMX is out of scope.
- `ae_validate.py` runs in the smoke test and in `ae_ci.py`.
Alternatives considered: Python-module data (not validatable or hot-reloadable); TOML (no stdlib writer); YAML (dependency).
Consequences: JSON has no comments, so notes go in an ignored `"_notes"` key.
Verification: Phase 7 migrates one level per commit. Golden and replay stay identical, and `ae_validate` passes.
