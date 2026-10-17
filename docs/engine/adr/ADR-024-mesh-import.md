# ADR-024 — Mesh import: glTF/GLB + OBJ → ae.mesh/1 through the asset pipeline

Status: ACCEPTED (Phase 11 step 11) · Engine: Retardovici Pulse Engine 6 Gold (RPE6)

## Question
§6.7 step 11 asks for a Blender import path, ADR first: glTF/GLB
preferred, OBJ minimum; the importer must go through the asset pipeline
and produce the engine's mesh format, with palette/scale lint and a
triangle budget.

## Decision
- **Importer**: `tools/ae_import_mesh.py`, stdlib only (no new deps).
  Reads binary/JSON glTF (`.glb`/`.gltf`, POSITION + indices accessors,
  material `baseColorFactor`) and Wavefront `.obj` (v/f, one material
  colour via `--color` or `usemtl` name lookup in the palette).
- **Engine mesh format**: `ae.mesh/1` JSON in
  `src/game/content/meshes/<id>.mesh.json` —
  `{schema, id, verts: [[x,y,z]...], faces: [[indices, [r,g,b]], ...],
  tris, source}`. Sets reference it with a `mesh` node
  (`ref`, `pos`, `yaw`, `scale`); the bridge builds an engine3d Mesh.
  JSON keeps the pipeline diffable, seeded and validator-friendly,
  like sets/grades/textures; no binary formats enter `content/`.
- **Palette lint**: every face colour is snapped to the nearest colour
  of the house palette (union of `content/textures/*.texture.json`
  palettes). Snaps farther than 24/255 per channel are reported; with
  `--strict` they fail. This keeps imported props on-palette with the
  textured sets (step 9) and the GL flat fallback identical in spirit.
- **Scale lint**: glTF/OBJ units are treated as metres. The importer
  prints the bounding box; height outside 0.05–40 m fails unless
  `--scale` corrects it. `--scale` is applied before export.
- **Triangle budget**: default budget 1500 tris per prop (error above,
  `--budget` overrides; the count is recorded in the asset and echoed
  by the set check when a set references the mesh).

## Consequences
Blender workflow: model → export glTF/OBJ → `ae_import_mesh.py` →
`ae.mesh/1` asset → reference from set data. No engine code changes
per prop. Rigged/animated glTF (skins, morphs) is out of scope —
static props only; characters stay on the rig (step 8).
