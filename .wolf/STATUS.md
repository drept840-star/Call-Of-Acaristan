---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1000
---
# STATUS — first-try

> Single source of truth for resuming work. Read this FIRST when starting a session.
> Update this file at the end of every work phase so the next `/clear` resumes in 1 read.
> Last updated: 2026-10-20

---

## ✅ Done

- **Ucilev actually shoulders the sniper.** The tower establishing shot had him
  holding it like a staff (one hand off it). The hold is solved against the rig:
  butt in the shoulder pocket (hand 0.34 m along the aim), fore-end yawed across
  the chest with the body yaw compensated so the muzzle tracks Volkov, support
  hand on the fore-end, head on the stock (new optional `head_x` pose key,
  default 0). He kneels at the parapet front edge so the roof no longer hides
  the weapon. Commit `cd6c0e0`; evidence `shots/_ucilev/beat_*.png`.
- **M6 interactive train performance.** Headless GL 800x560: combat 66 -> ~18 ms
  mean (p50 17.2-18.6, p95 ~22-24), cinematic 42 -> 16.4 ms (p50 15.8);
  first-frame (130 ms), cut-set (40 ms) and guard-spawn hitches gone.
  Mechanisms: RGBX opaque readback; `pack`/`add_packed` for viewmodel/decals/
  brass/train body; post-cut station pack memo + verbatim replay (snow, train
  drift, beacon and wires re-queued); transparent region-limited viewmodel
  overlay with an adaptive alpha-cover box; `bounds_m`/`bounds_cap_px` on FX
  callbacks + batched snow; door packed once; `prepare()` warm-up (shaders/FBO,
  static bake, rig templates, cinematic set memo). Commit `d6ab3da`.
  Evidence: `shots/_perf_m6/` (combat, tower, catch, vigil frames) plus the
  profiler numbers in the commit message.
- **M6 faces no longer read as pimples.** The M6 film finish stamped 1,400
  full-alpha near-black pixels over every frame, so close-ups looked like acne;
  it now uses `cutscenes.post3d.apply_post({"grain": 0.26})` (signed luminance
  grain, re-seeded at film rate, honours the Film Grain setting). All nine
  `m6films` finish calls pass the shot clock.
- **2D cutscene stubble** (`engine/anim/figure_kit.py::_face`) was 16 hard dark
  squares on the jaw; replaced with two nested translucent jaw patches (soft
  5 o'clock shadow, keeps the face's key/shade). Affects stubbled cast in every
  2D cutscene.
- **HD cheek bumps** (`engine3d/rig.py` HD head): the raised 3x4 cm skin-tone
  cheekbone boxes used by the M6 train rig read as pale pimples on the cheeks
  in the Volkov death close-ups; removed (brow ridge and chin planes stay).
- Evidence: `shots/_review_fix*/` (before/after face crops), `shots/_review_train_full/`,
  `shots/_review_train_fix/` (HD cheek fix at t=30.62);
  `tools/smoke_test.py` = SMOKE TEST: OK, `tools/ae_golden.py verify --kinds cutscene`
  = 339 shots, 0 failures.
- **Ucilev shoulders his rifle in the tower establishing shot.**
  `missions/m6/train3d.py` now has a train-local `_UCILEV_KNEEL_AIM` pose and
  `_draw_ucilev` derives `rifle_p` at runtime from the posed right-hand anchor
  to Volkov (`_volkov_at` + 1.05 m chest height), so the weapon pitch follows
  the target instead of being a hand-tuned constant. The shared sniper mesh
  and `POSES["kneel"]` are untouched (M5/M6 marksmen unaffected).
  **Measured, not yet rendered:** with the starting pose the eye sits 0.42 m
  from the optic (no weld), the stock 0.32 m off the shoulder and the left
  palm 0.53 m off the fore-end. A skeleton-only search over the 9 pose keys
  (no mesh build) reaches cheek 0.02-0.06 m, but needs spine 38-52 deg and a
  26 deg body twist, and the butt never closes past ~0.25 m: the tower is
  8.6 m above a target 9.5 m out, so the barrel must be pitched 42 deg down
  while the rig's rifle origin is the right hand. Open question: a train-local
  grip-origin rifle mesh would fix the butt/fore-end; pose keys alone cannot.
  Evidence: contact distances from `hum.pose_world` probes (no frames yet).

---

## 🚀 Next phase

**Goal:** playtest `--dev-mission6-shootout` on the target machine and confirm
60 Hz feel. If frames still exceed 16.7 ms, the remaining levers are:
1. Viewmodel as a persistent VBO + model-matrix uniform (saves the per-frame
   CPU transform and ~900 KB upload) instead of repacking rows.
2. Readback/grade floor: `_grade_play` is ~3.2 ms and the two GL passes pay two
   color reads; both are structural, not micro-optimizable.
3. `RES` 0.80 is the quality/perf knob; changing it alters train-scene pixels.

### Acceptance criteria
1. Combat and the canon cinematic hold <=16.7 ms mean on the target machine.
2. No hitch >2x median during the fight or the cut.

### Closed decisions
- Film grain is a per-pixel signed wobble, never sparse opaque pixels: at
  1000x700 close-ups specks read as skin blemishes. Reuse `post3d` grain.
- Keep the viewmodel in its own GL pass: merging it into the world pass at
  layer 7 makes the gun depth occlude every lower-layer sprite, and
  `_composite` then pays a subsurface copy/restore per snowflake (~16 ms).
- Snow uses `depth_test=False`: layer 4 is always in front of the layer-2 world.
- The post-cut set memo excludes the train body (the one moving part).

---

## 📁 Active architecture

- **Stack:** Python 3.13 + pygame-ce, in-house engine3d (GL 3.3 via moderngl,
  software fallback), sprite/film pipelines in `tools/`.
- **Key tables / modules:** `missions/m6/train3d.py` (scene), `cutscenes/
  m6world3d.py` (sets), `engine3d/gl.py` (pack/flush/composite).
- **Patterns:** see AGENTS.md; shared mutable state via owner-module imports.

---

## 🔧 Useful commands

```bash
python tools/smoke_test.py                                # SMOKE TEST: OK
python tools/ae_golden.py verify --kinds cutscene         # 339 shots, 0 fail
python tools/ae_normalize.py                              # AE NORMALIZE: OK
ACARISTAN_RENDERER=gl python tools/m6_shots.py shots/m6 boxcar --probe
```

---

## 📚 References

- `.wolf/cerebrum.md` — preferences + GL gotchas learned this session
- `.wolf/anatomy.md` — token-efficient file index
- `.wolf/buglog.json` — known bugs + fixes
