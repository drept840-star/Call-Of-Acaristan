# MASTER PROMPT - Rebuild the M5 finale ("m5_shadow_finale") to M2 quality

You are a senior cinematics programmer + layout artist working in the *Call of Acaristan*
repo (Python / pygame-ce / in-house `engine3d`). Your job: make the last cutscene of
Mission 5 look and feel at least as good as the M2 Route 12 ambush film
(`src/missions/m2/sniper3d.py`). Right now it looks cheap, empty and lifeless. The owner
is tired of it. Do not deliver "tweaks" - deliver a finale that reads like a film.

Read `AGENTS.md` first and obey it (PowerShell shell, facade/import rules, smoke test,
no hand-painted art, deterministic RNG, renderer rules). Those rules override anything here.

---

## 1. Files in scope

| File | Role |
|---|---|
| `src/missions/m5/finale_script.py` | Script: `LINES`, `CUTS`, `CUES`, `DURATION_MS=42000`, `FINAL_SHOT`. Dependency-free. |
| `src/cutscenes/m5shadow3d.py` | Renderer: actors, poses, walk, cameras, sky, rain, grade, subtitles. Entry `draw(s,t)`, `prepare()`, `draw_controls()`. |
| `src/cutscenes/m5harbour_art.py` | Set: `scene_meshes()`, `world_shell()`, `water_mesh()`, `actor_shadow()`. |
| `src/missions/m2/sniper3d.py` | **Reference for quality.** Read `draw()`, `_camera()`, `_actor_state()`, `keyed_pose()`, `pose_walk()`, `_draw_rain()`, `_make_vignette()`, `_draw_bars()`, `_blur/_flush_near_blur/_desat`, `SET.build/SET.sky`. |
| `tools/finale_compare.py` | Probe: renders both films to `outputs/finale_compare/` and prints luma/contrast/saturation/edge/frame-time. |

Dispatch: `cutscenes/engine.py` -> `scene == "m5_shadow_finale"` -> `m5shadow3d.draw`. `app.py`
calls `prepare()` and `draw_controls()`. Keep those three public signatures.

Keep the dialogue text and speaker order in `LINES`. You MAY retime `LINES`/`CUTS`/`CUES` and
change `DURATION_MS` (keep it 38-50 s), as long as audio cues stay in sync with on-screen action.

---

## 2. What is wrong (measured, not opinion)

From `python tools/finale_compare.py` + contact sheet:

1. **Maru walks into nowhere.** `state_at()` slides Maru from `(-2.7,0,-2.7)` 5.3 m along -X
   (yaw -90) through the service passage at x=-6.05, and she just *stops* at x=-8.0 in a blank
   3 m alley and stands there for the remaining ~36 s. No destination, no door, no boat, no
   look back, no exit from frame. The beat has no meaning.
2. **Walk cycle is bad.** `walking_pose()` only drives hip pitch + knee. No arm swing (arms are
   frozen constants), no pelvis bob/sway, no torso counter-rotation, no heel-strike/toe-off,
   no ankle, no weight shift, fixed 0.68 m stride regardless of speed, "wounded" is just a
   static hunched arm. Ucilev's retreat reuses the same legs pasted onto an aiming torso.
3. **The background is empty.** `world_shell()` is flat banded asphalt / river to +/-300 m.
   `scene_meshes()` is a handful of boxes: one quay, one wall, one warehouse front, a few
   crates. No skyline depth, no lit windows in volume, no vehicles, no cranes, no clutter,
   no light sources that actually light anything. Wide shots show grey nothing.
4. **Camera language is dead.** ~5 setups for 42 s. Both Biribel shots are the *same frame*
   (14.8 s and 23.9 s render identically); the Ucilev framing is reused 3x. Almost all shots
   are locked off. Biribel is centred, frontal, mugshot. **Ucilev - the reveal - never gets
   a close-up**: he is 26 m away (`UC=(-2,5,26.4)`), camera ~4.5 m off at fov 46.
5. **Acting is dead.** Biribel holds one `armed_pose` for the whole film (only a head turn at
   35 s). No reactions to lines, no breathing that reads, no weight shifts.
6. **Flat grade.** Ambient 0.65 => no form shading. Vignette alpha 18 (M2: ~190).
   Saturation 0.32 vs M2 0.17 (cheap teal cast). Fog starts at 32 m (M2: 14 m) so there is no
   aerial depth.
7. **Atmosphere invisible.** 74 rain streaks at alpha 22-34 (M2: 170 opaque streaks). No DoF
   (M2 uses `flush_split` / `flush_near_blur`). No practical-light glow, no mist, no steam.
8. **Wrong pixel look + slow.** Renders 1200x572 then `smoothscale`s down -> soft, not the
   game's look. M2 renders at half-res and upscales x2 nearest. M5 costs ~45 ms/frame vs M2 ~19.
9. **No film framing.** No fade from black, no location/time card, no speaker names even after
   the reveal, controls hint is the only UI.

---

## 3. The story beat (direct THIS)

Night, rain, harbour after the tunnel. Biribel has just got wounded Maru out to the river.

- **Escape (0-~7 s):** Maru limps to a *real* exit - a moored boat / a gap in the fence onto a
  lit pier / a ferry ramp - and is **visibly gone** (boards the boat, or exits frame through a
  gate that we see). She stops once and looks back at Biribel before leaving. Biribel covers
  her, rifle half-raised, scanning.
- **Threat (~7-10 s):** a red laser dot appears on Biribel's chest. He freezes. Rack focus.
- **Discovery (~10-12 s):** Biribel turns; long-lens push to the rooftop: Ucilev, prone or
  kneeling at the parapet with the marksman rifle, scope glint.
- **Dialogue (~12-31 s):** proper shot/reverse-shot. Ucilev gets a **tight close-up**
  (face readable, scope at cheek) and an over-the-shoulder from behind him onto tiny Biribel
  below. Biribel gets a 3/4 medium close-up and an OTS from behind him up to the roof. Every
  repeat of a speaker uses a *different, progressively tighter* framing. Each line gets a
  physical reaction (Biribel's grip tightens, breath fogs, head drops on "So why am I still
  standing?"; Ucilev lowers the rifle on "Not tonight").
- **Withdrawal (~31-35 s):** Ucilev stands, slings the rifle, walks off the roof and vanishes
  behind a vent/stairhead - an actual exit, not a slide.
- **Radio (~35-42 s):** Vasile on the radio. Biribel alone on the quay, wide shot, rain,
  the boat light far out on the water. Slow pull-out, fade to black.

---

## 4. Work packages (do all of them)

### A. Set dressing - kill the emptiness (`m5harbour_art.py`)
Authored by code, deterministic (`random.Random(seed)`), no textures painted by hand.
- **Foreground layer** in every shot: bollards, mooring rope coils, chain, puddles with
  practical reflections, fence posts, crates, a tarp, rain gutters dripping.
- **Midground:** gantry crane(s), stacked containers (varied colours from the locked
  palette), a parked Guard van with black paint over KRAP blue (story!), a forklift, lamp
  posts with real light cones, a small moored boat for Maru's exit with a lamp.
- **Background / skyline:** 3-4 depth bands of city silhouettes behind the warehouse and
  across the river with scattered warm windows, a church/tower landmark, red aircraft lights
  on a mast, distant moving car lights on a bridge. Use emissive faces + fog so bands read
  as layers. The sky must not be a flat gradient: add cloud bands lit from below by city
  glow (cheap: a few large soft quads or a baked surface like `SET.sky` in M2).
- **Water:** reflections of the practical lights as vertical broken streaks, moving with
  `water_mesh(t)`.
- Respect renderer rules: keep big slabs banded/`seg`-subdivided; nothing coplanar with deck
  (y=0), river (y=-0.82) or roof (y=5); no single frame-wide quads.
- Goal: in **every** camera setup there are at least 3 readable depth planes and something
  in the frame that is lit by a motivated source.

### B. Walk cycle (`m5shadow3d.py`)
Replace `walking_pose()` with a proper distance-driven locomotion:
- Planted feet (keep the world-anchored stance idea; zero foot sliding - verify by printing
  world foot positions during stance, drift < 1 cm).
- Heel-strike -> flat -> toe-off; ankle pitch; knee never hyper-extends; swing-leg knee bend
  peaks mid-swing.
- Pelvis: vertical bob (lowest at contact), lateral sway toward stance leg, yaw rotation;
  torso counter-rotates; head stabilises.
- Arm swing opposite to legs, amplitude tied to speed.
- **Wounded Maru:** a real limp - shorter stride and shorter stance time on the injured
  side, a dip on the bad leg, the bandaged right arm held to the body with the left hand,
  head down, one stumble-catch beat.
- Stride length/cadence scale with speed; start/stop with weight transfer (no pop).
- Ucilev's exit walk: rifle slung (rifle on back or low-ready), full body walk - not legs
  pasted under an aiming torso.
- Turns: feet step around the turn, the body doesn't spin on a planted pivot.

### C. Acting / blocking
- Use keyed poses like M2's `keyed_pose(keys,t)` with eased transitions. Biribel needs at
  least 6 distinct beats (cover, freeze, turn, aim up, lower slightly, head drop, radio
  reach). Ucilev at least 5 (aim, cheek-off-scope, speak, lower, stand+sling, walk off).
- Idle life: breathing (chest/shoulder), micro weight shifts, blinks if the rig supports it.
- Keep the existing two-link IK (`_solve`) for hands on the weapon; solve every frame.

### D. Cameras (`_camera`)
- 12-16 setups total, **no framing used twice**. Mix: establishing wide, long-lens
  discovery push, CU, MCU, OTS both ways, low angle up to the roof, high angle down from the
  roof, closing wide.
- Every held shot has motion: slow dolly/push-in, slight handheld drift on tense beats,
  rack focus. Respect the 180-degree line between Biribel and Ucilev.
- Rule of thirds, lead room in the look direction, eyes ~1/3 from the top.
- Ucilev CU: eye <= 2.2 m from his head, fov 24-32.
- Use DoF: `r.flush_split(...)` / `r.flush_near_blur(...)` exactly as M2 does for OTS and
  rack-focus shots.

### E. Lighting & grade
- Key/fill/rim per shot. Drop ambient to ~0.30-0.40, raise diffuse; add a cool rim from the
  harbour lights and a warm key from a practical lamp. Faces must have a light side and a
  dark side.
- Real vignette (port `_make_vignette`, alpha up to ~150-190).
- Desaturate toward M2 (target mean sat 0.15-0.22); keep the teal/sodium split but subtle.
- Fog start 10-15 m, fog colour matched to the sky horizon.
- Light glow on practicals (additive sprite like M2 `_draw_glint`), scope glint on Ucilev.

### F. Atmosphere
- Rain like M2 (`_draw_rain`): 150-200 streaks, opaque enough to read, fewer/softer in CUs.
- Rain splashes on the quay and ripples on puddles; drips from gutters.
- Breath fog for both men on their lines.
- Mist band over the river.

### G. Render pipeline
- Render at half res (500x? matching the film aspect) and upscale x2 with
  `pygame.transform.scale` (nearest), like M2 `RES_DIV=2`. No `smoothscale` for the final
  upscale.
- Target <= 25 ms/frame on GL, and the software fallback must still work
  (`draw(s,t,force_software=True)`).

### H. Film framing / UI
- Fade in from black (~0.9 s), location card "HARBOUR - EAST QUAY / 02:14 - RAIN" like M2.
- Subtitles: no name before the reveal; after the reveal show the speaker tag, `(RADIO)` for
  Vasile, same style as M2 `_draw_bars`.
- Letterbox bars consistent with M2.
- Final: fade to black on the last line, hold black ~1 s.

---

## 5. Hard constraints

- Do not change public entry points: `draw(s,t,force_software=False)`, `prepare()`,
  `draw_controls(s,paused,confirm)`, `FINAL_SHOT` keys.
- `draw` must be a pure function of `t` (scrubbable, clamps t, never mutates campaign state).
  Particles must be deterministic from `t` (no accumulated state), so pause/skip/seek work.
- Respect `reduced_motion` (no handheld, no rain motion, no shake).
- No `r._items`, no `pygame.OPENGL`, no new import cycles (lazy imports with `# lazy:`).
- Deterministic RNG only. No hand-painted assets.
- Do not touch M1-M4 or other M5 cutscenes.

---

## 6. Process (iterate visually - don't code blind)

1. Run `python tools/finale_compare.py` for the baseline. Save the contact sheet.
2. Extend the probe: render a frame every 1 s of the finale into
   `outputs/finale_compare/m5_full_XX.png` plus a contact sheet, and a strip of 12 frames of
   Maru's walk (side view) to judge the cycle.
3. Implement in order: **B (walk) + Maru's exit -> A (set) -> D (cameras) -> C (acting) ->
   E/F (light, atmosphere) -> G (pipeline) -> H (framing)**. After each package, re-render
   the contact sheet and LOOK at it. Fix what looks wrong before moving on.
4. Compare every shot against the M2 frames side by side. If a shot is less interesting than
   the M2 frame next to it, it is not done.

---

## 7. Acceptance criteria (all must pass)

- [ ] Maru visibly reaches and uses an exit (boat/gate) and is gone from the set by ~8 s.
- [ ] Walk strip: no foot sliding (< 1 cm stance drift), arms swing, pelvis bobs, limp is
      readable on the injured side.
- [ ] No two sampled frames from different shots are near-identical (probe: per-pixel mean
      abs diff > 8 between any two shots).
- [ ] Ucilev has at least one CU where his face is >= 12% of frame height.
- [ ] Every shot has >= 3 depth planes and no large flat empty region (> 30% of the frame
      within +/-4 luma of a single value).
- [ ] Probe averages within M2's range: luma std >= 26, mean saturation 0.15-0.22.
- [ ] GL frame time <= 25 ms average; software fallback renders without exceptions.
- [ ] `python tools/smoke_test.py` prints `SMOKE TEST: OK`; `python -m compileall -q src` clean.
- [ ] Audio `CUES` land on the matching action (footsteps on contacts, rifle handling on
      rifle moves, radio static on radio beats).

## 8. Deliverables

- Changed files + a short changelog per work package.
- Before/after contact sheets in `outputs/finale_compare/`.
- Probe metrics table before vs after.
- A list of anything you could not do and why.
