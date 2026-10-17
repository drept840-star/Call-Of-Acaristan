# Subsystem: `engine.render3d` + `engine3d` (Phases 6, 8)

Two halves: the **data** kernel in the engine tree, and the renderer
package `src/engine3d/` the game hosts it with.

```
engine.render3d
  scene3d.py         ae.set3d/1 model: Scene3D, build/from_dict/load_set3d/validate
                     (box / quad_xz / sprite3d prims; lights; camera anchors)
src/engine3d/        Renderer (GL when available, software fallback):
                     set_camera(pos, target, fov), begin(), add_dynamic(verts, faces),
                     flush(surface) into a host-owned buffer
src/game/render3d_bridge.py
                     set_prims(set_id) -> prims; renderer pool + failure latch live in
                     the host scene modules (cutscenes/m5martial3d._rend/_present pattern)
```

Phase 11 steps 1-4 (ADR-022): lighting presets (`content/lighting3d/`,
`engine.render3d.presets` - one-word `"lighting"` on a set, blend via
`bridge.set_lighting`), local point/spot lights (`light` nodes +
`attach_light` on emissive boxes; software per-face, GL shader, cap
8), footprint blob contact shadows (props + humanoids, both
backends), and baked AO folded into face colours at mesh build
(`seg` tessellation in data gives it faces). All four ride the
`quality_3d` setting (0 off / 1 low / 2 high).

Rules: set data carries every camera/mesh number (§10.10 — no magic
numbers in Python after Phase 8); a failed 3D take falls back to 2D
and latches the failure process-wide, so broken data shows up as a
~65% golden diff, never a silent pass. Backend determinism is gated
by `tools/ae_engine3d_parity.py`; the GL-vs-software diff is an
owner-machine run (`tools/engine3d_check.py`).

Phase 11 steps 5-11 (ADR-023/024): shot `"post"` data drives the
cinematic stack (`cutscenes/post3d.py`, grade assets in
`content/grades/`); weather is seeded closed-form set data
(`cutscenes/weather3d.py`, FX injected by hosts); cast shadows are
baked per-face raycasts (ADR-023); faces are parametric
(`engine3d.rig.EXPRESSIONS`, dialogue-driven mouth, clamped look-at);
palette textures (`content/textures/*.texture.json`, bridge planar
UVs, software nearest rasterizer — GL stays flat); set fields accept
`t` timeline expressions for animated props (`flicker` bulbs drive
emissive + attached light); imported props land as `ae.mesh/1`
(`tools/ae_import_mesh.py`, `mesh` nodes). `quality_3d` also scales
the internal render buffer (×1.0/×0.75/×0.6) for set-driven hosts.
