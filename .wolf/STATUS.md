---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1000
---
# STATUS — first-try

> Read this FIRST when resuming. Last updated: 2026-10-22

---

## Done (M6 cutscene anatomy pass, 2026-10-22)

- `m6world3d.reach` now uses `engine3d.ik.solve_arm` with an optional elbow
  pole; `m6films._OUT` (elbow out) / `_CROSS` (across body) poles on the
  boxcar, exit, door seat and Vasile handset. Vasile line 3 stays on the
  phone, free hand planted on the desk (was a 0.73 m hand pop). Pilot left
  out of the `m6_insert_jump` exterior (only a stray arm showed). Train
  catch: shoulder grip waits for Volkov's chest to land; smoke window d>=1.40.
- Probe: `python tools/m6_shots.py x all --clash` (body/body OBB depth).
  Residue <= 0.048 m: notebook handoff forearm contact, hidden-side 0.02-0.04.
- Gates: smoke OK, `test_m6_campaign` OK, goldens 339/0, compileall clean.

## Done (M6 lights + ending + heli pass, branch m6/train-polish)

- **GL lights respect walls.** `m6fx3d` light callbacks carry `fn.light`;
  `gl._render` packs physical depth into the colour alpha and `_composite`
  anchor-gates each light (3x3 kernel). Evidence: `tools/m6_halo_sheet.py`.
- **Halo redesign.** Hot core + ~10-level Bayer-dithered sodium->amber
  falloff, distance-sized; `beacon()` hard blink for aviation lights; ground
  spills are GL pools (`train3d._dynamic_pools`).
- **Ending E1-E11** incl. three-beat `m6_helicopter` (H1 pickup, H2 cabin,
  H3 turn-away), audio in `m6_audio.py`, pins in `meta.py`, tests, smoke.
- **`--m6-heli` visual pass.** H1: heli stays in frame, cold key + amber
  kicker on Biribel, wash lines/snow toned down. H3 rebuilt: camera east of
  lift-off, terrain-ridge hills, `capital(dx, dz)` skyline (windows/neon now
  face -z), curved west->north path, bigger nav strobes. H2 unchanged.
  Capital is on the right, hills on the left (plan doc said reverse; flip
  needs the camera west). `_turn_ridge` in `m6films.py` is now dead code.
- **Gates:** smoke OK; `test_m6_campaign` 53/53; cutscene goldens 339/0;
  compileall clean; `AE NORMALIZE` OK (dry run).

---

## Next phase

User sign-off on the new heli look and on the halo look.

1. `python acaristan.py --m6-heli` (or `python tools/m6_shots.py shots/_ending_final ending --probe`).
2. Halo sheet: `python tools/m6_halo_sheet.py` -> `shots/_m6_halo/sheet.png`.
3. After sign-off: delete `_turn_ridge`; update `m6-3d-art-direction` memory
   to "hot core + dithered smooth falloff, no rings".

### Known advisories
- E1 probe flags head luma (face averted until E2); H2 flags heli interior
  AABBs (not visual). ds-worker may fail with "CCR service did not come up";
  then run gates directly.

---

## Architecture

Python 3.13 + pygame-ce, in-house engine3d (GL 3.3 via moderngl, software
fallback). Scenes: `missions/m6/train3d.py`; sets `cutscenes/m6world3d.py`;
ending `cutscenes/m6films.py`; GL `engine3d/gl.py`. See AGENTS.md.

```bash
python tools/smoke_test.py
python -m unittest tests.unit.test_m6_campaign -q
python tools/ae_golden.py verify --kinds cutscene
python tools/ae_normalize.py
```

References: `.wolf/cerebrum.md`, `.wolf/anatomy.md`, `.wolf/buglog.json`.
