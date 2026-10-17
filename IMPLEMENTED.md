# Graphics rework — IMPLEMENTED (all five phases)

Companion to `graphics-review.md`. Everything below is **in the tree at
`acaristan-clean/`**, verified by `tools/smoke_test.py` (`SMOKE TEST: OK`) and
`python -m compileall -q src`, with before/after stills rendered from the real
draw path (`previews/`, index at the bottom).

Design invariant preserved throughout: **missing PNG ⇒ procedural fallback ⇒
the game still runs from a bare zip.** `ACA_ART=legacy` forces the fallback
everywhere, which is how the "before" column is rendered — it is not a
mock-up, it is the same build with the art tier switched off.

---

## Phase 0 — free wins

- **Static-layer bake** (`core/staticlayer.py`, new). M3's static world
  (floors, walls, shelves, cabinets, pipes, signage — ~1,100 draw calls/frame)
  is baked once into 512×512 chunks and blitted 2-4×/frame. LRU-capped at 24
  chunks; invalidated on stage/map change. Animated tiles consult
  `staticlayer.baking()` and emit a static base frame; the objective beacon's
  pulse runs per-frame in `_draw_m3_dynamic_tiles`.
- **Bundled fonts** (`core/config.py`). IBM Plex Mono (R/B/SemiBold) + Oswald
  (OFL) in `assets/fonts/`; `SysFont` only as a last resort. UI, HUD, dialogue
  and the menu are now identical on every machine.
- **`assets/m3_intro/` removed.** The opening briefing slideshow (six
  illustrated cards, location tag, caption, progress dots, ENTER/ESC) was cut
  from the game entirely — draw path, input handler, start flag and the asset
  folder are gone. Mission 3 now begins straight in the interrogation cell.
- **Pose caches** (`core/artpack.pose`). The player body is rendered once per
  (facing octant, walk phase, blink, recoil, gun) key and blitted; the five
  cutscene cast figures (`cutscenes/cast.py`) are cached per (pose, scale,
  facing). Reload/melee overlays and `ACA_ART=legacy` fall through to the
  procedural renderer.

## Phase 1 — surfaces

- **Tileset** (`assets/art/t_*`, `w_*`): 4 seeded variants per floor material
  (`. g O`), checker pairs for `K L Y M` matching the old `(col+row)%2` parity,
  4 wall variants with baked cap + base ambient occlusion, barrier + frosted
  glass. Applied in `_render_cell_bg` with the procedural path as fallback.
- **Props ported to sprites**: crate stack, barrels, cable coil, mop bucket,
  service cart, wall pipes — the six `_draw_bg_*` functions blit when the PNG
  exists. The art was already authored; it just stopped being drawn 60×/s.
- **9-slice panel** source (`panel9`) + `artpack.blit9slice` ready for UI work.

## Phase 2 — hero rooms

- **Bookshelf set** (`shelf_a/b/c`, 64×192): real spines with varied
  height/width/lean, gaps with horizontal stacks, plank highlights, baked
  cavity occlusion and dust. The archives' "equalizer bars" are gone.
- **Clerk office**: `cab_dossier` cabinets, `cork` notice board, engraved
  `plaque` (rendered with the bundled mono face at authoring time), plus
  flickering phosphor on the twin CRTs (4 content frames, gated while baking).
- **Comms**: `rack_0/1/2` server cabinets with per-unit face plates, vent
  slots and blinking LED clusters; `crt_0..3` monitors.

## Phase 3 — light

- **`core/lighting.py`** (new): half-res two-pass composite.
  - Grade pass (RGB-only multiply): per-wing near-white tint — warm sodium in
    Archives, phosphor green in Comms, cold fluorescent in the cell block —
    times a gentle radial falloff.
  - Light pass (additive, opaque premultiplied buffer): fixture pools with
    real penumbra, soft-falloff cones (archives case spotlight, interrogation
    chair), CRT/relay glow, muzzle-flash light.
  - **Dust motes** whose alpha is sampled from the light buffer, so they only
    sparkle inside light.
  - Per-fixture fluorescent **flicker**.
- **Sprite rain** (`core/config.py draw_rain`): wind-slanted streak sprites
  (slope matched to the drop velocity, two alpha tiers, length by speed)
  replace the 1-px lines wherever rain already falls. First attempt was too
  bright and splashed against the letterbox every frame; re-authored after
  playtest feedback to sit *below* the old procedural lines in prominence.
  Compare `previews/walk_rain_legacy.png` vs `walk_rain_new.png`.

## Phase 4 — bodies & UI furniture

- Player octant/phase pose cache (above) — per-frame polygon soup → one blit.
- Cast pose cache (above).
- **First-person hands** (`hand_open/pinch/grip/stamp`, 264×240) and the
  **VOSTRAL dossier** (`dossier_plain/evidence/confirmed`) authored for the
  pickup cinematic's FP view; three-tone shading, rim light, sleeve cuff.
- **Icon set** 32×32 (`i_molotov, i_dossier, i_keycard, i_relay, i_radio,
  i_bandage, i_arrow`) + `artpack.icon()` for prompt/waypoint/HUD use.

---

## Files added / touched

| File | What |
|---|---|
| `src/core/artpack.py` | new — sprite registry, tileset access, 9-slice, pose cache, `ACA_ART` switch |
| `src/core/staticlayer.py` | new — chunked static-world bake |
| `src/core/lighting.py` | new — light buffer, grades, cones, motes, flicker |
| `src/core/config.py` | bundled fonts; sprite rain |
| `src/missions/m3/draw.py` | tileset + sprite hooks, static-layer composers, lighting fixture table + composite, dispatcher wrapper |
| `src/missions/m3/flow.py` | mission start state (briefing slideshow removed) |
| `src/entities/player.py` | pose-cached `draw`, procedural `_draw_body_uncached` |
| `src/cutscenes/cast.py` | `_pose_cached` decorator on the five cast figures |
| `tools/make_art_pack.py` | new — authors all 84 sprites, palette-locked, 1:1 |
| `tools/render_previews.py` | new — headless before/after stills via `game_core.game_draw` |
| `tools/compose_sheets.py` | new — labelled contact sheets |

Regenerate everything:

```
python tools/make_art_pack.py                 # 84 sprites, ~384 KB
ACA_ART=legacy python tools/render_previews.py legacy
python tools/render_previews.py new
python tools/compose_sheets.py
python tools/smoke_test.py                    # gate
```

Added weight: **art 384 KB + fonts 588 KB**. `build.bat` bundles `assets/`
wholesale, so packaging needs no change. (The 736 KB `assets/m3_intro/` cards
were deleted with the briefing slideshow.)

## Known limitations (honest list)

- The **player body is deliberately NOT sprite-cached.** An octant/phase pose
  cache was tried and reverted after playtest feedback: bucketing the facing
  angle made the drawn gun snap in 45° steps while bullets flew at the true
  mouse angle. `Player.draw` is fully continuous/procedural again. The five
  cutscene cast figures remain pose-cached (their facing was already a
  boolean, so nothing quantises).
- Rack LED / CRT flicker is frozen inside baked chunks except where a
  per-frame push exists (clerk CRTs, fixture glows); comms racks blink only
  via the lighting pass.
- The light buffer grades and lights; it does not yet do shadow casting
  (sight cones still own gameplay visibility).
- Icons are authored and loadable but only lightly wired (HUD helpers); prompt
  tags still text-first by design (`_draw_dialogue_panel` deliberately avoids
  UI furniture).

## Preview index (`previews/`)

| File | Contents |
|---|---|
| `preview_world_before_after.png` | 4 wings × (legacy \| new): clerk office, catalog stacks, comms, cell block |
| `preview_cinematics_ui.png` | chair-break before/after, menu with bundled fonts |
| `preview_sprite_pack.png` | the 48-piece contact sheet of the generated pack |
| `acaristan-clean/previews/*_legacy.png / *_new.png` | full-res 1000×700 stills per scene/tier |


---

# Post-rework lanes (playtest-driven + verification)

## Lane 1 — shadow casting
`core/lighting.py` now ray-marches 56 angles per fixture against a tilemap
solidity predicate (`_m3_solid_world`: walls/barriers/doors) and multiplies the
additive buffer by the resulting visibility polygon, so light stops at walls.
Masks are cached per (fixture, door-signature, radius); the signature is
`sum(door.anim_progress)*4`, so opening a door invalidates exactly once.
Also fixed a real bug found here: lights were blitted into the half-res buffer
at full-res size, making every pool **2x** its intended radius.

## Lane 2 — finished the half-done art
- **Doors**: `door_leaf` (56x56, ribs/bars/viewport/keypad) blitted as a left
  sub-rect whose width tracks `1 - open_progress`, so the slide keeps all
  authored detail; `door_open_inner` for the breached/open state with jamb
  occlusion. Procedural fallback intact.
- **Machines un-frozen**: comms racks (3 LED frames), server-console LEDs and
  battery-room LEDs are excluded from the static bake and cycle per frame;
  clerk CRT phosphor likewise, plus a purple spill light while live.
- **Icons wired**: prompt tags take `icon=` (radio / dossier / keycard in use)
  and the objective waypoint bobs the `i_arrow` sprite over its ring.

## Lane 3 — verification
- `tools/bench_frame.py`: 240 timed frames after warm-up. Measured here:
  **bake+art 6.24 ms/frame (160 fps)** vs **no-bake+art 11.32 ms (88 fps)** —
  the static layer removes ~45% of frame time; **bake+legacy 4.39 ms** prices
  the art tier at ~1.9 ms/frame. `ACA_STATIC=off` bypasses the bake.
- `tools/golden.py` + smoke check `golden_images`: 40x28 grayscale signatures
  (16 levels, +/-1 tolerance, 2% budget) for archives/comms/cell under
  `ACA_FREEZE=1`. Negative-tested: legacy art vs new baseline fails at
  26-152 px off; same-tier runs 0-1 px off. Re-baseline with
  `GOLDEN_UPDATE=1 python tools/golden.py`.

## Lane 4 — motion
- Enemies: continuous walk sway driven by actual per-frame displacement
  (phase advances only when the body moves), so nothing quantises — the same
  lesson as the player aim-snap revert.
- Cutscene cast: `_pose_cached` accepts `act_t` and applies a subtle
  breathing bob at blit time; wired into the three Volkov beats in
  `cutscenes/m3ops.py`.

---

## Mission 4 — "The Aftermath" (campaign finale)

The full fourth mission is in the tree and verified by `tools/smoke_test.py`
(`SMOKE TEST: OK`, six `mission4_*` checks) and `python -m compileall -q src tools`.

- **Package:** `src/missions/m4/` — a PEP 562 re-export facade over
  `meta → maps → world → flow → systems → draw`, following the M3 layout.
  Two procedural `list[str]` maps (40×40 curfew street, 24×20 radio-station
  interior), M3 tile grammar, border-sealed.
- **Content:** three stages (`STAGE_AFTERMATH` regroup → station crossing +
  KRAP–MAG liaison dialogue + jammer → `STAGE_COMMIT` transmitter siege). The
  finale is a hold clock (`M4_HOLD_SECONDS = 90`), not a boss: loyalist
  fireteams stream from 3 doors (≤6 concurrent) with a ported marksman
  laser telegraph, while a diegetic PA/arrest ladder narrates Retardovici
  ordering Balaceanu's arrest on air. Biribel never sees or kills Balaceanu.
- **New cutscene art** (`src/cutscenes/m4aftermath.py`, the `m3ending.py`
  per-scene `surface, t` idiom): `_draw_m4_city_curfew`, `_draw_m4_arrest_screen`,
  `_draw_m4_maru_silhouette`, `_draw_m4_roof_dawn` — dispatched from
  `cutscenes/engine.py` and re-exported from `cutscenes/__init__.py`. Each
  non-title-card shot is headless-rendered in the smoke gate.
- **Campaign chain:** `game_core` routes MISSION4 first; `save_system`
  records `MISSION_4`; `app.py` wires the intro/ending cutscenes,
  `--dev-mission4`, slot-select resume (`MISSION_3 → M4`,
  `progress=="m4" → checkpoint`, `MISSION_4 → FULL CAMPAIGN COMPLETE`).
- **Cross-package rule:** zero imports from `missions.m3` internals —
  enemy-role tuning, typewriter cadence and the sniper-laser idiom are copied
  with `# ported from` comments. Beat sheet: `docs/MISSION4_PLOT.md`.
