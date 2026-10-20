# MASTER PROMPT - Raise the 2D cutscene floor (M1-M4 + chair)

You are a senior 2D cinematic artist and pygame engineer working in the *Call of Acaristan*
repo (Python / pygame-ce / in-house `engine3d`). Your job is **not** to convert anything to
3D and **not** to add story. Make every existing 2D cutscene look intentional, using the
techniques the best existing 2D scenes already prove. The owner judges by playing; a green
smoke test is not acceptance.

Read, in this order: `AGENTS.md`, `SKILLS/Game Graphics Art Director...md`,
`SKILLS/create-beautiful-pygame-graphics...md`, `docs/MASTER_ACTION_PLAN.md` section 7
(T6 defects), then this file. `AGENTS.md` overrides anything here.

---

## Current state and target

Best 2D bar: the interrogation chair (`src/cutscenes/chair.py` - composite zoom at line 78,
handheld drift at 129, light pool, dust, breath, rim) and M4 roof dawn
(`src/cutscenes/m4aftermath.py:550` - dolly, warm grade, silhouettes, reduced-motion lock).

Weakest 2D: the M1 intro in `src/cutscenes/engine.py` (flat rectangles, no depth, no camera),
the Route 12 checkpoint (`src/cutscenes/route12.py:964` - static plate, empty truck), and the
repeated aftermath (`src/missions/m2/meta.py:99,117,124` - same frame three times).

2D owners: `route12.py`, `chair.py`, `m3cell.py`, `m3ops.py`, `m3ko.py`, `m3broadcast.py`,
`m3ending.py`, `m4aftermath.py`, and the scene chain in `cutscenes/engine.py`. Shots dispatch
through `core.cutscene_registry`; keep that architecture. Do **not** touch M5/M6 3D takes or
the 3D renderer.

## Non-negotiables

- No 3D conversion. No new image assets: procedural only, deterministic RNG
  (`random.Random(seed)` or the named engine stream), never global RNG for visuals.
- No changes to dialogue text, speaker order, VO IDs, story beats, or cast identity.
  `engine.anim.SPECS` is the source of truth; never hand-draw a person.
- Follow `AGENTS.md`: shared mutable state lives in one owner part; do not inline logic in a
  facade `__init__.py`; check import order before adding a cross-part import.
- Game time only via `engine.core.now_ms()` / `now_s()`; never `time.time()` or
  `pygame.time.get_ticks()` in draw code.
- Respect `STATE.reduced_motion`: no dolly, crop-jump, or shake when it is set.
- Keep public signatures used by `app.py`: `draw_cutscene_scene`, `prepare` where present,
  and the `register_scene_renderers` tables.

## Work packages - one commit each, gates after each

**P0 - Baseline evidence (no src edits).** Render every 2D scene at 25/50/75% plus a motion
strip. Use `tools/ae_gauntlet.py`; add a small review tool only if needed. Write under
`shots/cutscene_review/` (gitignored). Record luma, contrast, edge energy, and a face ROI per
frame. Do not touch `tests/golden` yet. These are the frames to beat.

**P1 - Kill the one-size-fits-all look.**
- `draw_vignette` ignores its `strength` argument (`src/core/config.py:338`), so the
  `quiet_ui` 80 vs 180 intent at `src/app.py:2953` is dead. Pre-render 4-5 strengths
  (60/100/130/180/220) and select the nearest; keep the settings toggle behaviour.
- `draw_cutscene_scene` overwrites the per-shot `lighting` colour at
  `src/cutscenes/engine.py:22`. Make it tint the plate or the scene fill instead of being
  discarded, without washing out subtitles.
- Add `post` blocks (`grade`, `vignette`, `grain`, `bloom`) to 2D shot data, applied by
  `cutscenes.post3d.apply_post` (`src/cutscenes/post3d.py:99`). Data lives in
  `src/game/content/timelines/*.timeline.json` for M1/M2 and `src/missions/mN/meta.py` for
  M3/M4. Tone per mission: M1 cold/desaturated, M2 sodium/ash, M3 teal/fluorescent, M4 amber.
- Acceptance: quiet scenes are visibly less crushed; each mission has a distinct palette; no
  face ROI p5 below 25 luma.

**P2 - One shared 2.5D camera.** Add `src/cutscenes/camera2d.py`, dependency-free (pygame,
math, `engine.core` only), imported before `route12` in the facade and named in the facade
docstring. Provide `push(surface, plate, zoom, focus, shake)`, `drift(t, amp, seed)`, and
`parallax(layer, camera, depth)`. Cache scaled plates; one transform per frame maximum; pick
one scaling policy (render at 2x, smoothscale down) and use it everywhere instead of the
current mix of `smoothscale` and `scale`. Pre-render static plates once; no per-frame gradient
loops; add ordered dither to large gradients to kill banding. Apply to every 2D shot: a
motivated move, or a deliberate locked frame with foreground occlusion and atmosphere. A
locked frame with nothing moving for over a second is a failure.

**P3 - Acting.** Use `figure_kit.draw_character` with its animation args
(`src/engine/anim/figure_kit.py:624`) for breath, blink, look, reach, bow. Static poses keep
the cached `cutscenes.cast` wrappers. Every named character gets breath + blink + an eye line;
each speaker gets a reaction beat before or after the line. No new faces or wardrobe changes.

**P4 - Typography and sound.** Replace `pygame.font.SysFont("Impact", 56)` in
`src/cutscenes/engine.py:368` with the bundled `font_title` (Oswald) or `pixfont`; cache
renders; keep wrapping/line height at 1000x700 with no overflow. Add an optional `ambience`
key to shot data and honour it in the cutscene ambience block (`src/app.py:2907-2929`), using
only existing audio assets. Add 2-4 foley cues per scene only where the asset already exists.
Do not invent or synthesize audio.

**P5 - Visible T6 repairs.** Give the three `route12_aftermath` entries distinct variants or
cut one. Add a variant parameter to `_draw_route12_checkpoint_base` (`route12.py:964`) so the
truck/lane state is not the same empty slab. Fix the unreachable `route12_tanker` dispatcher
branch (`engine.py:274`). Optional: support `max_ms` in the cutscene player, set only on shots
with no VO and no exit condition.

## Verification (repo root, after every package)

```
python tools/smoke_test.py                  # SMOKE TEST: OK
python -m compileall -q src
python tools/ae_normalize.py                # dry run: AE NORMALIZE: OK
python tools/ae_gauntlet.py                 # clean report
python tools/ae_golden.py verify --kinds cutscene
```

Do not silently recapture `baseline_v0`. Any intended look change will move cutscene
goldens: report the exact failing ids, then capture a named set only after owner approval
(`--set cutscene_polish_p1`, etc.) and explain the pixel diff in the commit.
Inspect every package's contact sheet at 100% and 2x, plus a grayscale pass. Compare against
`chair` and `m4_roof_dawn` as the bar, not against the previous frame.

## Definition of done

Every 2D scene in M1-M4 plus chair has: a distinct grade/light, a camera idea, at least one
acted beat, no dead frame over one second, and no repeated identical shot. No 3D conversion,
no story changes, no new hand-drawn cast, no unapproved golden baseline change. Each commit
covers one package and names the before/after contact-sheet paths.

Do not touch: M5/M6 3D takes, `engine3d`, `src/audio/voice_manifest.py`, dialogue text,
facade ordering except the new `camera2d` import, or `tests/golden/baseline_v0`.

Report back per package: files changed, gates, contact-sheet paths, what changed visually,
and what you did NOT do.
