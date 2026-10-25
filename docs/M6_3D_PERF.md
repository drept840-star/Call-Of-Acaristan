# M6 playable 3D scenes - performance pass (2026-10-24)

Scope: the two **playable** engine3d scenes of Mission 6 - the shoulder-cam
train scene (`src/missions/m6/train3d.py`) and the rail-yard fight after it
(`src/missions/m6/yard3d.py`). The cutscene films are untouched.

## Where the frame time actually goes

Measured with `tools/m6_phases.py` / cProfile / instrumented moderngl calls
(software-GL sandbox, 1000x700 window, 640x448 internal buffer):

| phase (train scene, 8 guards) | ms/frame | note |
|---|---|---|
| FBO colour readback (`mgl read_into`) | 57 | `_render` -> `_composite` needs pixels |
| FBO depth texture read (`self._depth.read`) | 0.4 | |
| geometry draws (`VertexArray.render`) | 13 | rasterisation |
| `flush_overlay` (viewmodel second pass) | 10 | own readback + upload |
| `_composite` (depth-masked sprites) | 1.7 | |
| grade LUT (`apply_lut`) | 3.1 | |
| `present_crisp` (x2 + smoothscale) | 2.5 | |
| HUD / radio / objective | 1.1 | |
| sky repaint (`_sky`) | 0.7 | |
| the scene's own Python queues | ~7 | actors, FX, lights |

The yard fight is the same profile (43k tris, 62 sprites): readback 15 ms,
draws 10 ms, composite 1.5 ms.

Every one of the first eight rows is proportional to the **buffer area**, and
that buffer is 640x448 because the scene is a deliberate PS2-style frame that
gets upscaled 1.56x with a sharp-bilinear filter. So the resolution is the
lever, not the triangle count: dropping to 0.48 cuts the frame by 30 %, to
0.40 by 42 %.

Also found: `quality_3d` (the options setting that gates lights/shadows/AO in
every other 3D surface) was **not read at all** by either M6 scene, so a
player on a weak machine had no way to dial M6 down.

## What changed

1. **`src/missions/m6/perf.py` (new) - frame governor.**
   * Tier from `quality_3d`: 2 -> 0.64 (authored), 1 -> 0.56, 0 -> 0.48.
   * `plan()` runs once per scene inside its warm-up (`TrainScene._warm_up`,
     `YardScene.begin`) - before the first visible frame, because every step
     of the measurement re-bakes the static set (~100-180 ms). It times two
     real frames and steps down while the draw is over `BUDGET_MS` (12 ms),
     stopping early if the smaller buffer does not actually buy anything (the
     software backend is polygon-bound, not pixel-bound - it stays at 0.64).
   * `govern()` - a live watchdog on the presented frame interval (median over
     60 frames, OS clock, "profiling" per AGENTS.md). Above 22 ms/frame it
     drops one tier, at most 2 times per scene, never back up. This is the
     part that handles "my GPU is fine on an empty set but not in the fight".
   * `detail()` scales optional per-frame flourishes (snow counts, glitter,
     point-light cap) with the tier.
   * Determinism: `ACA_FREEZE=1` (golden / parity / smoke harnesses) bypasses
     measurement and watchdog entirely.
2. **`train3d.py`** - `buffer_size()` + a `_renderer()` that rebuilds the
   renderer when the scale changes (dropping the set bake/memo), `RES`/`RW`/`RH`
   kept as the authored ceiling so `tools/trailer_rpe6` (which rebinds them)
   still pins the buffer; snow counts through `_perf.detail()`;
   `_perf.govern("m6_train")` at the end of `draw()`; `_perf.watchdog_reset()`
   in `begin()`.
3. **`yard3d.py`** - measures in `begin()` (instead of drawing straight into a
   scratch surface), same watchdog.
4. **`m6world3d.py`** - `drop_renderer_caches()` so a replaced renderer can
   never inherit a stale bake/pack memo keyed on a recycled `id()`.
5. **`engine3d/gl.py`** - `_draw_dyn()` concatenates its 30-80 small chunks
   into one reusable staging array and hands the array to `Buffer.write`
   instead of `np.concatenate(...).tobytes()` (two full copies of the whole
   dynamic buffer per pass, twice a frame in the train scene).
6. **New dev tools** (not CI gates): `tools/m6_bench.py` (frame bench for
   train / yard / films, `--profile`), `tools/m6_phases.py` (per-phase table
   that separates readback from Python), `tools/m6_prof.py` (cProfile run).

## Measured (software-GL sandbox; a real GPU is ~10x faster on the draw side)

| scene | 0.64 (authored) | 0.56 | 0.48 | 0.40 |
|---|---|---|---|---|
| train, 8 guards | 94.6 ms | 79.4 | 66.4 | 55.0 |
| yard fight | 64.3 ms | - | 46.2 | - |

The `quality_3d` ladder alone therefore gives 1.4x on the weakest tier, and the
watchdog finds the tier on hardware I cannot see.

## Gates

* `python tools/smoke_test.py` -> `SMOKE TEST: OK` (M6 slice, train viewmodel,
  ADS muzzle, scope subject, death beat, impacts, guard death, redeploy).
* `python -m compileall -q src` clean.
* `python tools/engine3d_check.py` -> GL/software parity OK, worst 3.3 %.
* `python tools/ae_ci.py` - same failing rows before and after the patch on
  this machine (api snapshot / unit tests / golden / replay / loop parity have
  no baselines in the slim tree); the 3D bench row went 34.4 -> 29.2 ms.
* Pixel identity at the authored tier (`ACA_FREEZE=1`, software):
  `tools/m6_shots.py train --at=12,22.9,26.2` and a 60-frame yard A/B are
  **byte-identical** to the unpatched tree.

## Knobs

| env | effect |
|---|---|
| `quality_3d` (options) | 2 / 1 / 0 -> 0.64 / 0.56 / 0.48 |
| `ACA_M6_RES=0.40` | force a fixed scale, no measurement |
| `ACA_M6_DRS=0` | keep the setting's tier, no measurement, no watchdog |
| `ACA_M6_DEBUG=1` | print the resolved scale and the frame medians |
| `ACARISTAN_RENDERER=software` | if the GPU path is the problem, test this |

## If it is still slow

`ACA_M6_DEBUG=1` prints `M6 3D: m6_train: NN ms/frame median at scale X`.
If that reads `GLRenderer` and still >22 ms after two steps, the cost is
outside the buffer (HUD/audio/Python) and the next lever is the per-phase table
from `python tools/m6_phases.py train`; if it reads `SoftwareRenderer`, the GL
context failed and the fix is driver/`ACARISTAN_RENDERER=gl`, not the scene.

## Pass 2 (same day): the stutter, not the average

Report after the first pass: "still stutters". Average frame cost was no longer
the whole story - a *spike* every so often reads as a hitch even at 40 fps, so
this pass hunted one-off frame costs. Found and fixed:

| cause | cost | fix |
|---|---|---|
| **Governor tier switch rebuilt the renderer and re-packed the whole set** | **150-165 ms freeze, up to 3x per scene** | `GLRenderer.resize()` / `SoftwareRenderer.resize()`: the projection is resolution independent, so a tier change is just new colour/depth textures - baked set, rig templates and VBOs survive. Measured: switch frame 165 ms -> 67 ms (= a normal frame), and the resized frame is pixel-equal to running at that tier from the start (mean diff 0.003) |
| M6 one-shots synthesised at first play (numpy) | 16 ms truck, 8 ms departure, 7 ms whiz, ~38 ms total, each on the beat it happens | `M6TrainAudio.warm()` pre-synthesises all 20 sounds during the scene's load |
| New (rig, expression) GPU template built on the beat | ~3 ms each, on every emotional close-up | `_warm_up` builds every face the scene switches to |
| Visible pop on a tier change | one frame | `_snapshot_for_blend()` + `_resolution_blend()`: two-frame 35/70 % cross-fade |

Also: the ladder gained a 0.34 tier and the watchdog a third step, so a weak
machine ends at 340x238 (~20 fps equivalent of headroom) instead of bottoming
out at 0.40 and staying slow.

New diagnostics (for a machine I cannot see):

* `python tools/m6_diag.py [train|yard] [frames]` - prints CPU, GL vendor and
  renderer string, resolved tier, buffer size, frame median/p95/p99/max, the
  count of frames over 33/50/100 ms, and a per-phase table. One command, copy
  the output.
* `build/m6_hitches.log` - every frame over 3x this machine's median is logged
  with its timestamp, frame time, resolved scale and the phases that were live
  in it. Written automatically while playing the two scenes.
* `ACA_M6_HUD=1` - one-line on-screen strip: backend, scale, ms, fps.

Verification for pass 2: `SMOKE TEST: OK`, `engine3d_check` OK (worst 3.3 %),
authored-tier pixels still byte-identical (train shots x3, 60-frame yard A/B),
and the hitch probe (`tools/m6_hitch.py train 900`) now reports
**0 spikes over 1.6x median, max/median = 1.4** where it previously logged
three 95-105 ms frames from tier switches.

## Pass 3 (same day): "the spikes are even worse" - my fix was the hitch

Correct call, and it was my fault: pass 2 left an **adaptive loop in the frame
path** - a warm-up measurement, a frame-interval watchdog and a spike log that
appended to disk. On a real driver, re-targeting a GL framebuffer *while the
player is being shot at* is a hitch generator, and the log wrote to disk on
exactly the frames that were already late. All of it is now **off by default**:

| was | now (default) |
|---|---|
| `plan()` measured 2-10 draws at load and could pick a tier | no measurement; the tier comes straight from `quality_3d` |
| watchdog lowered the scale mid-fight (each step = new GL textures + FBO) | inert unless `ACA_M6_AUTO=1`; and then: 90-frame window, 6 s cooldown, max 2 steps |
| `build/m6_hitches.log` appended on every spike | opt-in only (`ACA_M6_HITCHLOG=1`) - no disk I/O in the frame path |
| cross-fade after a tier change | only ever runs when a tier actually changed (never, by default) |
| `_renderer()` recomputed light cap/glitter every frame | recomputed only when the tier changes |

Default behaviour is now: **static scale from `quality_3d`, one decision at
load, zero per-frame machinery** - and at `quality_3d=2` (the shipped default)
the M6 scenes are **pixel-identical to the unpatched build** (verified against
a fresh copy of the original zip: `m6_shots train --at=12,22.9,26.2`, maxdiff
0 on all three frames). Spike probe at that tier: **0 frames over 1.6x median**.

### One more spike source, found while looking (not M6-specific)

`_present_frame()` - the manual present used when the window is fullscreen or
maximised - allocated a 1000x700 copy **and** a window-sized scale target on
every single frame, then threw them away. On a 1440p display that is ~15 MB of
allocation churn per frame. Both surfaces are cached now (repainted/reletterboxed
only when the window changes). Output verified pixel-identical at 1000x700,
1280x800, 1920x1080 and 2560x1440; per-frame cost 6.55 -> 4.02 ms at 1440p,
3.90 -> 0.32 ms at 1000x700.

### What to do now

1. Play the patched build as shipped (static, `quality_3d=2`). If it still
   stutters, my patch is not the cause - nothing of mine runs per frame beyond
   two dict lookups.
2. If you want the cheaper buffer, it is now a plain setting: `quality_3d=0`
   renders M6 at 0.48 (or force any value with `ACA_M6_RES=0.48`). No
   measurement, no switching, no spikes.
3. Send `m6_report.txt` (written by `python tools/m6_diag.py`) - it has the
   machine, the GL renderer string, the real backend, the per-phase table and
   the count of frames over 33/50/100 ms, which is what decides the next move.

## Pass 4 (2026-10-24, real GPU): the CPU work around the GL calls

Report: "the M6 3D scenes lag like crazy, frame drops". First numbers from the
real machine (RX 7800 XT, i7-12700KF; passes 1-3 ran in the software-GL
sandbox). Real loop, `tools/m6_loop_probe.py --dev-mission6-train 600`: median
32 ms, p95 58, p99 91, 48 frames over 50 ms. The card was not the limit (draw
calls ~0.5 ms); the frame was full-buffer CPU passes over the 640x448 frame
plus a handful of one-off builds.

| cause | cost | fix |
|---|---|---|
| grade LUT walked the surface column-major (a row of stride per pixel) and cast a uint16 index to intp inside every `take` | 3.5 ms, up to 9 | `m6fx3d.apply_lut`: memory order, intp, the 3 channels on 2 helper threads + main. Bit-exact. ~1 ms |
| yard re-sent its memoized live set (39k tris, 9.9 MB) to the card every frame | 2.2 ms | `GLRenderer.add_resident`, used by `pack_memo_replay`: uploaded once, drawn from its own VBO. Frame pixel-identical |
| ~51 light sprites a frame, 72 % (yard) / 26 % (train) outside the frame, each probed by a 9-sample Python loop and then run through its halo callback | ~1 ms | `_light_targets` (one numpy pass; equal to the scalar probe on 26k lights) and a cull when the declared box misses the frame (0 culled lights painted anything) |
| `_set_uniforms`: `name in prog` walks every member, `prog[name]` makes a wrapper, ~35 writes x 3 calls | 0.4 ms (0.9 in a slow state) | per-program uniform objects + last written values |
| 500 px halo build | 20 ms on the frame that met it | `_halo_img` quadrant maths, pixel-exact over 768 configs, 2.7x |
| first hit built the full-screen hurt vignette | 30-43 ms | built in `TrainScene.prepare()` |
| wind gust synthesised at t=8 s (`core.ambience`), room tone at frame 1 | ~50 ms | `ambience.prewarm(mission)` from both scenes' load |
| objective banner re-measured and rebuilt every frame (all missions) | 0.4 ms | cached panel, same blits in the same order |
| `_alpha_cover` used `np.nonzero` on the gun region | 0.25 ms | `any()` reductions |

Result, real loop: train median 17.4 ms (the 60 fps cap), p99 22.1, 3 frames
over 33 ms (the first two are the load); yard 16.6 / p99 18.9. Isolated
`draw()` in a fast machine state: yard 16.0 -> 11.6 ms, train 15.6 -> 12.4 ms;
under sustained fire 15.4 / 15.8 ms. Output is bit-exact against the old code:
cutscene goldens (345 shots), gameplay goldens (34), `SMOKE TEST: OK`, 56 M6
tests; the unit suite's only errors are the 3 old `GLRenderer.stats` ones.

Measuring on this PC: runs swing up to 2x with background load (`opencode`
holds a core), so every number was repeated and decisions were taken from
interleaved A/B runs inside one process, never run-to-run.

Still open:

* Viewmodel second pass (`flush_overlay` 1.6-2.0 ms + `_draw_viewmodel`
  0.8 ms): fold into the main pass with the gun rows on layer 7 and the
  reticle/flash as overlay sprites. ~1.4 ms, needs a pixel A/B on the gun.
* GL-native BGRA upload/readback (`tobytes` 0.65 ms, `frombytes` + blit
  0.45 ms). `present_crisp` (1.9 ms) is pygame C code that holds the GIL, so
  threads do not help it.
* `cig_smoke` scales 5 puffs a frame in the Volkov close-ups (~3.5 ms, cinematic).
* A radio line with no file in `assets/voice/_radio_cache` freezes 130-500 ms on
  its first play (pure-Python filter chain in `audio/voice.py`). `python
  tools/build_radio_cache.py [--speaker NAME] [--limit N]` builds them; ~0.7 s
  and 1.5 MB per line, 367 lines, not run for the whole set.
