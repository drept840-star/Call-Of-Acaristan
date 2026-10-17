# Phase 11 report — 3D visual upgrades, steps 1–4 (RPE6)

Status: **DONE in the sandbox** (2026-10-16) — the phase's minimum
exit: steps 1–4 of the §6.7 track shipped to the acceptance bar, in
order, each usable from data alone, with before/after proof sheets,
a quality setting, bench numbers, a deliberate golden re-baseline
and a clean gauntlet. Steps 5–11 were not started (the track's rule:
a step that starts must finish — none did). Owner reference-machine
runs (GL diff, 10 ms-class bench certification, owner golden
re-export per B-038) remain owner-side, stated plainly below.

## What shipped (ADR-022)
1. **Lighting presets** — `ae.lighting3d/1` in
   `src/game/content/lighting3d/` (night_interior, office_day,
   exterior_overcast, exterior_night_rain + 2 aliases, duplicates
   rejected); `engine.render3d.presets` resolve/override/blend;
   sets switch mood with `"lighting": "office_day"`; M0's outro
   cross-fades night_interior → office_day via the bridge.
   Unit proof: `tests/unit/test_presets.py` (5 tests).
2. **Several lights per scene** — `light` nodes (`kind: point|spot`)
   and `attach_light` on emissive boxes; software per-face falloff +
   spot cones, cap 8 strongest (low quality: 4); the GL shader
   implements the same model for 4 lights on dynamic geometry
   (declared divergence: GL baked-static geometry, ADR-022 §2).
   Depot lamp + bench spot; office desk lamp + sconce now light
   their surroundings for real.
3. **Soft contact shadows** — footprint-derived blob shadows for
   floor-resting props + every humanoid, both backends, blurred
   cached discs. **Incident during development:** an unclamped disc
   allocation (actor near the camera plane) OOM-killed a parity run;
   fixed with viewport clamps + a bounded cache, re-verified.
4. **Baked corner darkening** — AO folded into face colours at mesh
   build (0.7 m wall-base band, 0.55 m floor-to-wall falloff),
   `seg` tessellation in set data gives it faces to live on. Side
   benefit: the finer wall tessellation fixed a painter occlusion
   bug — the office GUARD banner decal now wins against the back
   wall; visible in the step-4 sheet.
- **Setting:** `quality_3d` 0/1/2 through the Phase 9 settings path.
- **Bench:** `tools/ae_bench3d.py` — office3d avg 31.3 ms / depot3d
  9.7 ms in the sandbox at quality high (caps 38/14 ms sandbox,
  owner budgets 20/12 ms in `tools/bench_budgets.json`), CI row added.
- **Fixes along the way:** B-039 — Mission 0's scaffold camera spent
  most of the outro outside the back wall staring at a blank face;
  replaced with an interior path (game-side host, logged in BUGS.md).

## Proof + review (Appendix D style: pass / note)
| Step | Proof sheet | Review |
|---|---|---|
| 1 presets | `previews/upgrades3d/step1/sheet.png` | PASS — office warms via `office_day`; one-word switch demonstrated in both sets |
| 2 local lights | `previews/upgrades3d/step2/sheet.png` | PASS — desk lamp pools on the desk; depot lamp/spot shape the room; note: per-face banding on huge faces, mitigated with `seg` tessellation in data |
| 3 contact shadows | `previews/upgrades3d/step3/sheet.png` | PASS — feet and furniture grounded in office + film; subtle on dark floors by design |
| 4 baked AO | `previews/upgrades3d/step4/sheet.png` | PASS — wall bases and corners sit down; banner occlusion fixed as a side effect |
| All | `previews/upgrades3d/final_sheet.png` | The before/after the owner asked for |

## Deliberate re-baseline + gates (sandbox, 2026-10-16)
- Golden: `ACA_GOLDEN_SET=sandbox_linux` captured 373 shots for the
  upgraded look, verify 373/373 (`AE GOLDEN: OK`). The owner set
  stays B-038-flagged; the owner's deliberate re-baseline happens
  with its re-export.
- Gauntlet: **clean** (92 shots × 2 fresh offsets, 5 gameplay
  segments × 30 shifted frames, no S1/S2) —
  `docs/engine/evidence/phase11/gauntlet.txt`.
- Engine tree: Mission 0's Phase 10 zero-diff hash
  (`e26ff0bd…`, 82 files) is preserved in
  `tools/ae_mission0_check.py` as the historical proof; the pin was
  re-frozen to `57dc9dd9…` (83 files) for the Phase 11 kernel
  addition (presets), per the check's own instructions. AE MISSION0
  still passes: playthrough + outro render with all upgrades on.
- API snapshot re-recorded (80 modules, 547 names: presets module +
  render3d facade). Boundaries OK (W1 49 =). Units 285 OK.
- Full CI: see `docs/engine/evidence/phase11/final_gate.txt`.

## Not done / owner-side
- Steps 5–11 not started (post-FX, weather, GL cast shadows,
  character polish, textures, animated props, Blender import).
- GL backend: point/spot shader path + blob compositing are written
  but only software-verified here; `tools/engine3d_check.py` on the
  owner machine is the GL proof, and the engine3d parity CI row
  continues to gate the software backend's determinism.
- Owner golden re-export (B-038) + deliberate owner re-baseline;
  bench certification against the 20/12 ms owner budgets.

---

## Addendum 2026-10-16 — Steps 5–11 + low-end pass (sandbox)

Steps 5–11 executed in order, each to the same bar (data-only use,
proof in `previews/upgrades3d/stepN/`, setting/tier behaviour, bench
number, deliberate re-baseline, gauntlet clean). Full CI green:
`docs/engine/evidence/phase11/final_gate_steps5-11.txt`; gauntlet
`gauntlet_steps5-11.txt` (93×2, 5×30).

| Step | Delivered | Proof | Review |
|---|---|---|---|
| 5 cinematic post-FX | `cutscenes/post3d.py`: grade LUTs (`content/grades/*.grade.json`), seeded grain, vignette, bloom, distortion; DOF via renderer `flush_split` keyed from shot `"post"` data; accessibility caps (`film_grain`, `flash_reduction`) honoured | `step5/sheet.png` | PASS — grain/vignette/grade/DOF all visible; 5 unit tests |
| 6 weather & atmosphere | `cutscenes/weather3d.py`: seeded closed-form rain, smoke/steam/dust emitters, fog layers; puddle fakes in bridge; new yard set + `m0_yard3d` outro shot; depot steam | `step6/sheet.png` (yard row, weather on/off) | PASS — rain/fog/steam/puddle read in yard; 4 unit tests. NOTE: rain delegates to host-injected FX module (W1 fix — shared code no longer imports `m5fx3d`) |
| 7 cast shadows | ADR-023: baked per-face ray-vs-AABB shadows into face colours — both backends, zero frame cost after a fingerprint cache (12.5 ms one-time bake on depot); `cast_shadows` flag in set data | `step7/sheet.png` | PASS — crate shadow wedge + darkened yard bench/crate; 2 unit tests. GL shadow maps rejected with evidence in ADR |
| 8 character polish | rig: `EXPRESSIONS` (8 parametric faces), `set_expression`, `mouth_flap`, `solve_look` (±38°/−14..30° clamps); set humanoids take `expression`/`speaking`/`look_at`; mouth follows shot speaker at 50 ms/char; yard guard posted | `step8/sheet.png`, `step8/faces.png` | PASS — expression grid + look-away/down panels read; 5 unit tests |
| 9 surface textures | `ae.texture/1` palette assets (`content/textures/`, generator `tools/ae_textures_gen.py`); planar world UVs in bridge; software nearest affine rasterizer (shared surfarray lock + stride path for big quads); GL keeps flat colour (declared) | `step9/sheet.png` | PASS — concrete/wood/asphalt read at depot+yard; 3 unit tests. NOTE: textures cost ~+12 ms depot tier-2 sandbox (stride path cut 55→27 ms); tier 0/1 are the low-end answer |
| 10 animated props | any numeric set field is a timeline expression in `t` (hosts pass shot `t` + `set_params`); `flicker` on `attach_light` drives emissive bulb + light from `bridge.flicker_at`; depot monitor (TV) with animated emissive colour + light; bake fingerprint quantised so sway doesn't rebake | `step10/sheet.png`, `step10/anim_strip.png` | PASS — TV cycles blue→purple across t=900/1700/2500; 4 unit tests |
| 11 Blender import | ADR-024: `tools/ae_import_mesh.py` (glTF/GLB + OBJ, stdlib only) → `ae.mesh/1` assets (`content/meshes/`); palette snap lint, metre scale lint, 1500-tri budget; `mesh` set node; barrel fixture in the yard | `step11/sheet.png` | PASS — imported barrel renders on-palette in yard; 4 unit tests (incl. hand-built GLB) |

### Low-end pass (owner request: "people have shit PCs")
- `quality_3d` 0/1/2 now also drives **internal render scale** for
  set-driven 3D hosts (`bridge.render_size_3d`: ×1.0 / ×0.75 / ×0.6 of
  the 480×270 buffer, recreated on tier change) plus the existing
  gating (lights cap, shadows, AO, textures, DOF, post, weather).
- Per-tier bench rows recorded in `tools/bench_budgets.json`
  (office3d/depot3d × q2/q1/q0, sandbox-recorded 2026-10-16; depot
  q0 = 3.9 ms vs q2 = 27.3 ms sandbox). Sandbox p99 caps carry
  documented load-jitter headroom; avg is the regression signal.
- The legacy M5 film hosts keep their authored 0.6× buffer.

### Gates (sandbox, 2026-10-16)
- `AE CI: OK` (all rows incl. boundaries W1 49 =, API 80/547,
  loop 7/7 after recapture of the slimmed sandbox set, golden 373/373,
  parity OK, mission-0 zero-diff pin re-frozen per step with
  justification in `tools/ae_mission0_check.py`: final `7069c19d…`).
- Units 312 OK; smoke OK; gauntlet clean.
- Golden sandbox set deliberately re-captured at each step.

## Not done / owner-side (updated)
- Owner golden re-export (B-038) + deliberate owner re-baseline;
  bench certification against the 20/12 ms owner budgets (sandbox
  numbers are regression guards, not certification).
- GL backend: cast-shadow bakes and palette colours carry over (they
  are mesh data); textures/post are software-path features — GL renders
  the same sets flat-shaded. `tools/engine3d_check.py` on the owner
  machine remains the GL proof.
