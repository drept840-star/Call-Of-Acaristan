# ADR-023 — Cast shadows: baked per-face raycasts (no shadow maps)

Status: ACCEPTED (Phase 11 step 7) · Engine: Retardovici Pulse Engine 6 Gold (RPE6)

## Question
§6.7 step 7 asks for cast shadows, suggesting an ADR first: shadow-mapped,
stencil, or reject — with its own golden set if parity is off, and a
measured budget call under §6.22.

## Options considered
1. **GL shadow mapping** — real-time, dynamic; but the GL backend is
   unverifiable in the sandbox (owner GPU only), its shading already
   diverges from software (dynamic-only lights), and a shadow map would
   add a second, larger divergence. Software backend gets nothing.
2. **Stencil shadow volumes** — needs manifold geometry + depth-fail
   robustness; our meshes are open boxes/quads. Rejected.
3. **Baked per-face raycasts** — at set-build time, cast one ray per face
   centre toward each `cast_shadows` light; occluded faces are darkened
   in their baked face colour (same mechanism as the step-4 AO bake).
   Sets are axis-aligned box worlds, so occlusion is an exact ray-AABB
   slab test. Cost: one-time at build (measured below), ZERO per frame.

## Decision
Option 3. Shadows are data (face colours), so BOTH backends render them
identically — parity stays green and NO separate golden set is needed.
Dynamic actors keep blob shadows (step 3); dynamic/flickering lights do
not re-bake (their blob + emissive pulse carries the effect).

Rules:
- A light casts only when its data says `"cast_shadows": true`
  (light nodes in set JSON; point/spot kinds).
- Quality gate: `quality_3d` 0 disables the bake (blobs also off there);
  1/2 bake identically — the cost is at build, not per frame, so low-end
  machines pay nothing while playing.
- Self-occlusion: a face never shadows itself (own prim excluded, ray
  origin offset along the face normal, near-hit epsilon 0.02 m).
- Shadow strength is a bake constant (0.45 multiplier) — flat-shaded,
  resolution follows the set's `seg` tessellation like light gradients.

## Budget evidence (§6.22)
Bake cost measured with `tools/ae_bench3d.py` build timings on the
depot set (the first `cast_shadows` consumer); frame cost is zero by
construction (bench3d frame numbers must not move — verified at the
step gate).

## Consequences
Golden sets change deliberately (darker occluded faces) → re-baseline
with the step. GL keeps parity for statics; real-time GL shadow maps
remain a possible future ADR if the GL backend becomes primary.
