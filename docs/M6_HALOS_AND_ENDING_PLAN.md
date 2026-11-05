# M6 plan - halos that stay behind walls, and an ending the player can follow

Status: IMPLEMENTED 2026-10-22 on `m6/train-polish`, with the defaults in
section 8. Workstream A used a physical-depth alpha channel rather than the
layer-2 encoding in A2 (the layer slot over-occluded higher-layer window
panes); A3's anchor kernel is 3×3 to hold the +0.5 ms budget. Evidence:
`shots/_m6_halo/sheet.png`, `shots/_ending_final/_sheet.jpg`,
`shots/_ending_fb/_sheet.jpg`. Written 2026-10-22 from a read of the code and the playtest screenshot
(train scene, GL backend: an orange banded ellipse painted up the side of the
carriage, lamp discs floating in front of walls).

---

## 0. Context

Three complaints from the playtest:

1. **Lights go through stuff.** Lamp halos, red beacons, window glows and haze
   draw over geometry that should hide them.
2. **The halos look horrible.** The stepped "PS2 halo" from commit `2a3be34`
   reads as flat target rings and big flat ovals, not as light.
3. **The ending film is weak and hard to follow**, the helicopter shot most of
   all: the player does not know where Biribel is, why he is reading a file,
   what the file means, who Maru is talking to, or that he is on the
   helicopter at all.

Goal: fix (1) at the root in one place, redesign (2) so it still fits the
late-PS2 art direction, and rebuild the ending chain (3) as a short film with
clear cause and effect, ending on a helicopter sequence that is the best shot
of the mission instead of the weakest.

---

## 1. Diagnosis (what the code actually does)

### 1.1 Why halos show through walls - root cause

- Every light sprite in M6 is queued with `layer=_fx.FX_LAYER`, and
  `m5fx3d.FX_LAYER = 6` (`src/cutscenes/m5fx3d.py:36`). That is ~130 call sites:
  81 in `missions/m6/train3d.py`, 13 in `missions/m6/yard3d.py`, 29 in
  `cutscenes/m6world3d.py` (incl. `warm_lamp`), 9 in `cutscenes/m6films.py`.
- The GL composite (`src/engine3d/gl.py` `_composite`, ~L852) decides per pixel
  whether a sprite is hidden with `occ = depth < enc`, where
  `enc = _enc(layer, z) = ((7 - slot) + z/far) / 8`.
  The layer slot dominates the encoding: a layer-6 sprite encodes to
  0.125..0.25, while layer-2 world geometry sits at 0.625..0.75.
  **World depth is never smaller than a layer-6 sprite's enc, so world
  geometry can never occlude a light sprite.** Every halo paints over every
  wall, carriage and person between it and the camera.
- The comments in `train3d.py` (~L3861, "depth-masked floor sprites") show the
  intent was depth masking; the layer choice silently disabled it. In the
  software backend layer 6 was only a painter order, which is why it looked
  fine before the GL port.
- To confirm in step A0 (not assumed): what layer/encoding the GL world pass
  writes into the depth texture for static, dynamic and rig draws.

### 1.2 Why the halos look bad

From `src/cutscenes/m6fx3d.py`:

- `_stepped()` makes 2-3 **flat** bands (`_LAMP` 0.42 / 0.20 / 0.08) with a
  1-pixel Bayer edge. On a dark night frame each band edge is a visible ring,
  so every lamp reads as a target.
- `glow()` clamps the radius to **28 px** regardless of distance
  (`min(max_px, 28, ...)`), so near and far lamps have the same halo; close
  lamps look tiny, far ones look huge relative to their mast.
- `haze()` is the same flat disc scaled up: `_YARD_HAZE` uses
  `haze(..., 15.0 m)`, i.e. a screen-filling flat oval.
- `window_glow()` uses `power=3` squircles; at ground height it is a
  screen-facing billboard, so a "floor spill" stands up vertically and paints
  an ellipse up the carriage side (the oval in the screenshot). Some ground
  spills are gated off on GL (`train3d.py` L1050, L1062, L3866, L4013;
  `yard3d.py` L329) but others are not, e.g. carriage window spill
  (`train3d.py` ~L3947, y=0.10), door spills (~L4099), truck spills
  (~L4140, ~L4151), guard flashlight floor spot (~L4201).
- `light_shaft()` is a stack of flat discs; `warm_lamp()` stacks glow + haze +
  shaft additively on one point, so every lamp is three overlapping flat shapes.
- Halos add on top of the GL sodium pools (`set_pools`), so the area under a
  lamp is lit twice and clips to flat cream.

### 1.3 Why the ending does not read

Current chain (`src/missions/m6/meta.py` `mission6_ending_shots`, renderers in
`src/cutscenes/m6films.py` L1186-1397):

| # | scene | what is on screen | problem |
|---|---|---|---|
| 1 | `m6_customs_terminal` 5.2 s | slow push into a CRT showing CRT_LINES: VELICU, B. / KIA Y-2 / CALLSIGN UCILEV NADGOB IERDNA | No establishing shot: we jump from the train to an unexplained office. No reason he is looking this up. The reveal (callsign = his name reversed, a dead top-of-class Guard) is left for the player to decode from small CRT text in 5 s. |
| 2-5 | `m6_radio_vasile` x4 | Biribel at the desk with a handset; only the 4th line cuts to Vasile's office | The player never sees the call being placed, never sees the evidence (the Route 12 leaf), and only meets Vasile on his last line. |
| 6 | `m6_radio_maru` 4.2 s | same desk, another angle | Nothing shows that this is a second voice cutting in on a different channel, or that Biribel chooses Maru over Vasile. |
| 7 | `m6_helicopter` 5.2 s | locked wide from 66 m: a small helicopter yawing 100 deg | Biribel is not shown boarding or aboard; the airframe is tiny; the "away from the capital, toward the hills" choice is not framed; it just ends. |
| 8 | `title_card` | WHITEOUT / THE LAST SIGNAL | fine |

Plot intent (`docs/MISSION6_PLOT.md` "The Call"): Biribel walks back to the
customs post, learns who shot Volkov, confronts Vasile, gets Vasile's offer,
does not answer, Maru tells him to go to ground, and Maru's helicopter takes
him away from the capital (Vasile and Retardovici) toward the dark hills (M7,
Bodi's farm). Every one of those beats needs to be *seen*, not inferred.

---

## 2. Workstream A - Light occlusion (root fix, one place)

**Principle:** a light sprite is a world object at its lamp's depth. It is
hidden per pixel by anything nearer, and it disappears entirely when the lamp
itself is hidden (that is how PS2-era games handled flares and coronas).

A0. **Probe first.** Add a temporary debug path (env flag, removed before
    commit) that, for one train frame and one yard frame, dumps: the depth
    value at each light anchor, the enc the sprite uses, and an image with
    each light sprite tinted by call site. Use it to (a) confirm 1.1 and
    (b) identify exactly which sprite produced the screenshot's oval.

A1. **Mark light sprites, do not touch call sites.** In `m6fx3d`, every light
    constructor (`glow`, `sodium_lamp`, `window_glow`, `crt_bloom`, `flash`,
    `haze`, `light_shaft`) tags its draw fn with `draw.light = True`. Sparks,
    motes, smoke, blood stay untagged.

A2. **Composite lights against world depth.** In `gl.py _composite`, when a
    sprite fn has `light`:
    - compute `enc` with the world slot (layer 2) at the sprite's `zeff`
      instead of its queued layer, so nearer geometry and actors hide it per
      pixel;
    - keep the queued layer for *sort order* only (lights still draw after
      the world, so additive blending is correct).

A3. **Anchor visibility gate.** Before drawing a light, sample the depth
    buffer in a small kernel (3x3 or 5x5 px) round `(sx, sy)` and compare to
    the anchor's world enc minus a small bias. Visible fraction `v` in 0..1:
    - `v == 0`: skip the sprite (lamp behind a wall: no halo bleeding round
      the corner);
    - `0 < v < 1`: scale intensity by `v` (lamp half-hidden by a pole);
    - the bias is per light type: lamp heads sit inside their own emissive
      box, so the bias must clear that box (~0.25 m) without letting a wall
      1 m in front pass.
    Cheap: one small slice per light, done before the costly subsurface copy.

A4. **Temporal smoothing of `v`.** Keep a tiny per-anchor cache (key =
    quantised anchor position) and ease `v` over ~80 ms so lights do not pop
    as the camera or a guard passes in front. Reset the cache on cuts
    (the renderer already resets per shot via `begin()`/set memo).

A5. **Ground spills: no more billboards on GL.** Every `window_glow` whose
    anchor is at ground height (y < ~0.15 m) is a floor pool pretending to be
    a sprite. On GL convert each to a `set_pools` entry (cap 32, already
    supported in `engine3d/core.py set_pools` and the GL shader):
    - static spills (carriage windows, doors, truck parked lamp) go into
      `SET_POOLS` / `LAMP_POOLS`;
    - moving ones (truck headlights, guard flashlight floor spot) are added
      per frame through `T._light(..., pools=...)` like the yard already does;
    - if a scene would exceed 32 pools, drop the farthest from the camera.
    Software backend keeps the sprites (painter order is fine there).

A6. **Software backend.** No change beyond A1 tags; it never had a depth
    buffer for sprites. Note it in the module docstring.

A7. **Perf guard.** Partially occluded lights pay the subsurface copy path in
    `_composite`. Measure with the existing perf harness (STATUS: combat
    ~18 ms, cinematic ~16.4 ms). Budget: no more than +0.5 ms mean. If over,
    move fully-visible lights onto the fast path (already exists: `occ.any()`
    false) and cap haze bounds.

Files: `src/engine3d/gl.py`, `src/cutscenes/m6fx3d.py`,
`src/missions/m6/train3d.py`, `src/missions/m6/yard3d.py`,
`src/cutscenes/m6world3d.py` (pool lists only).

---

## 3. Workstream B - Halo redesign (still PS2, no longer rings)

Reference look: late-PS2 night scenes (MGS2/3, Silent Hill 3 street lamps,
SOCOM): a **small hot core**, a **short smooth falloff**, colour that cools
toward the edge, and very little glow in the air unless there is fog.
Pixel honesty comes from posterising the falloff into many fine steps plus
ordered dither, not from 2-3 visible bands.

B1. **New falloff profile** in `_stepped` (keep the name and cache):
    - intensity `I(r) = core(r) + (1 - r)^p` with `p` ~2.2, quantised to
      8-12 levels, Bayer-dithered *across* every step so no ring shows;
    - colour ramp per sprite: `LAMP_WHITE` core -> `SODIUM_PALE` -> `SODIUM`
      -> `AMBER` at the rim, instead of one colour scaled;
    - result: reads as a soft-edged pixel halo at 600x273/RES 0.80, not as a
      target.

B2. **Distance-aware size.** Replace the hard 28 px cap with
    `rad = clamp(radius_m * scale, min_px, max_px)` where `max_px` scales with
    proximity (near lamp ~40 px, far lamp floor ~3 px core only) and far
    halos fade intensity with `z` (lamps beyond ~60 m become cores only,
    matching fog).

B3. **Glow budget per lamp.** One lamp = one core + one halo. Remove the
    `warm_lamp` triple stack: keep glow; keep haze only when the set has fog
    (`r.fog_end < 60`) and at ~half the current intensity; drop
    `light_shaft` from lamps except the two hero lamps on the platform (the
    shaft redesigned as a single tapered quad with vertical dither, not
    stacked discs).

B4. **Haze discs.** `_YARD_HAZE` 15 m discs become a gradient band baked into
    the sky/fog (`_w.night` already draws a sodium horizon tint: raise that
    instead) - no screen-sized sprites.

B5. **Window glows.** Lit windows already have emissive geometry. Shrink
    `window_glow` to a thin dithered rim (`_WINDOW` bands -> ~1.15x the pane,
    low level) or skip it beyond ~25 m. No squircle billboards.

B6. **No double-lighting.** Where a GL pool lights the ground under a lamp,
    the halo must not reach the ground: clip lamp halos to `radius_m <= mast
    height * 0.35`, and lower pool `hot` so the centre is warm, not cream.

B7. **Colour discipline.** Keep the palette (`missions/m6/palette3d.py`), but
    red beacons get a smaller halo and a slow blink with a hard on/off (they
    are aviation lamps, not fire). Searchlights keep `LAMP_WHITE` core plus a
    cool rim.

B8. **Tuning sheet.** A dev contact sheet (tool script, not shipped) renders
    one lamp at 5 m / 15 m / 40 m / 80 m, on dark sky, on a lit wall, and half
    occluded by a pole, before/after, so tuning is done on one image instead
    of in play.

Files: `src/cutscenes/m6fx3d.py` (main), `src/cutscenes/m6world3d.py`
(`warm_lamp`, `night`), `src/missions/m6/train3d.py` (`_YARD_HAZE`, lamp
radii), `src/missions/m6/yard3d.py` (`_perimeter_sprites`).
M5 is untouched (`m5fx3d` is not edited).

Memory note: `m6-3d-art-direction` currently says "hard halos". After the
user signs off on the new look, update that memory to "small hot core,
dithered smooth falloff, no rings".

---

## 4. Workstream C - The ending, rebuilt so it reads

### 4.1 Story beats the film must show (in order)

1. Biribel came back alone to the customs post, at night, after the train.
2. He wants to know who fired the shot that killed Volkov.
3. The Guard file says: the shooter's callsign is a dead Guard's name spelled
   backwards. Ucilev = Velicu, top of his class, "killed in action" two years
   ago. A ghost the Guard keeps.
4. He has the Route 12 leaf with Vasile's code on it. He calls Vasile.
5. Vasile admits it, justifies it, and offers a way in to Retardovici.
6. Biribel does not answer.
7. Maru cuts in on another channel: not tonight, go to ground.
8. Biribel cuts Vasile off. That is the choice of this mission.
9. Maru's helicopter picks him up outside the post.
10. In the air he looks back at the capital's lights, then the helicopter
    turns away from them, toward the dark hills (M7).
11. Title card.

### 4.2 New shot list

Existing scene ids stay (the doc calls them a contract); new ids are added
for new beats. Durations are targets, all `auto_advance` where silent.

| # | scene id | len | content |
|---|---|---|---|
| E1 | **`m6_customs_return`** (new) | 4.5 s | Exterior, customs post at night, snow. Wide on the frozen car queue; Biribel walks into frame alone, notebook in hand, up to the lit doorway. Tag: `KRAP BORDER CUSTOMS // 04:10`. Sound: wind bed, snow steps, door. Answers "where are we and why". |
| E2 | `m6_customs_terminal` (reworked) | 7.5 s | OTS on Biribel at the terminal. He types `UCILEV` into a search field (typewriter on the CRT, key clicks). Push into the CRT. File appears line by line (CRT_LINES). Then the CALLSIGN line animates: letters of `UCILEV NADGOB IERDNA` slide and reorder into `ANDREI BOGDAN VELICU`, and the NAME field `VELICU, B.` and STATUS `KIA - Y-2` highlight in sync. Hold 1 s. The reveal is now shown, not hidden in small text. |
| E3 | `m6_radio_vasile` v0 (reworked) | 4.4 s | Insert first (1.2 s inside the same shot): the Route 12 leaf on the desk, Vasile's code circled; Biribel's hand lifts the handset, the set's channel lamp lights `GUARD HQ`. Then his line: "Route 12 went out on your code." |
| E4 | `m6_radio_vasile` v1 -> Vasile's office | 6.6 s | "...Three hundred men..." on **Vasile**, at his window over the capital, handset to his ear (reuse `vasile_office`). We meet him on his first line, not his last. |
| E5 | `m6_radio_vasile` v2 | 4.4 s | "You'd have done the same." Back on Biribel, closer; his face does not move. Hold the silence. |
| E6 | `m6_radio_vasile` v3 | 7.2 s | "Retardovici is at the mansion in two nights..." Vasile turns from the window to his desk map; the mansion marked. Ends on Vasile waiting for an answer. |
| E7 | **`m6_radio_silence`** (new, no line) | 2.4 s | Biribel, handset at his ear, says nothing. Only the static and Vasile's breathing. Caption-free beat: the "no answer" made visible. |
| E8 | `m6_radio_maru` (reworked) | 4.2 s | Static burst; the set's second channel lamp flicks on (`OPEN CHANNEL`), the needle jumps. Maru (voice only): "Not tonight. Go to ground." Tag: `MARU // OPEN CHANNEL`. |
| E9 | **`m6_cut_line`** (new) | 3.0 s | Close on the set: Biribel's thumb flips the switch, the `GUARD HQ` lamp dies. He folds the notebook into his coat, stands. Sound: switch click, static cut, rotor faint outside. The choice, on screen. |
| E10 | `m6_helicopter` (rebuilt, 3 beats inside, see 4.3) | ~12 s | Pickup, cabin, turn-away. |
| E11 | `title_card` | 2.2 s | unchanged |

Total ~58 s (today ~38 s). Every new and reworked shot gets a hand-authored
2D fallback (`_fb_*`), as the module contract requires.

### 4.3 The helicopter, properly

One scene id `m6_helicopter`, `min_ms` ~12000, three beats with hard cuts
inside the renderer (the boxcar exit already switches cameras by time):

**H1 - Pickup (0-4.6 s).** Outside the customs post. The Huey descends into
the floodlit lot, nose light on, rotor wash: snow blown *outward* from under
the rotor (new radial mode for `snow3d`, or `dust_motes` with radial drift),
lamp halos swaying in the wash. Maru in the open door, beckoning (his rig
already exists from M5? confirm `hum("maru")`; otherwise a hooded figure).
Biribel runs low under the disc, one foot on the skid, hauled in by Maru's
hand. Camera: low, behind Biribel, tracking with lag, slight shake.
Reuse: `hover_pos`, `heli_xform`/`helicopter` anchors (`door_sill`,
`skid_top_r`), the insertion rotor-wash sprites from `_insert_heli`.

**H2 - Cabin (4.6-8.2 s).** Inside the door, as in the insertion
(`seated_door`, `heli_seat`). Biribel seated, notebook on his knee. Through
the open door, the capital's lights sit on the horizon. He looks at them
(head turn with `_look`). Maru across from him, says nothing. The door
slides shut on the capital (door anim on the airframe: new `door` float
0..1 in `helicopter()`). Sound: door slam, rotor bed muffles.

**H3 - Turn away (8.2-12 s).** Exterior wide, but framed for meaning:
capital lights on the left third, dark hills on the right third, helicopter
centre and *large enough to read* (scale it for the shot or bring the camera
to ~30 m instead of 66 m). Red/green nav lights and a white strobe (new halo
kit, occluded properly) so the airframe reads at distance. The helicopter
banks right, its nose swings from the capital to the hills
(`heli_at("m6_helicopter")` path rewritten as a turn of ~140 deg with a climb),
camera pans with it so the city slides out of frame and the hills fill it.
The nav lights shrink into the dark; fade to the title card.

Technical fixes in the heli itself:
- rotor blur: keep `blur` but make it a dithered disc with the new halo
  shader rules (no flat additive oval);
- airframe lighting: add a cockpit glow (dim green instrument light) inside
  the glazed nose so the silhouette has a readable front;
- nav lights through the airframe must be occluded (Workstream A covers it).

### 4.4 Text and UI clarity

- Location/time tags on every location change (`_w.finish(..., tag)`):
  `KRAP BORDER CUSTOMS // 04:10`, `GUARD HQ // VASILE'S OFFICE`,
  `MARU // OPEN CHANNEL`, last shot keeps `THE LAST SIGNAL`.
- Radio captions: speaker names stay; add a small channel label to the
  caption for radio shots (`meta.py` already has `"radio": True`); confirm
  CutscenePlayer shows it, otherwise prefix speaker as `VASILE (RADIO)`.
- The CRT reveal (E2) uses the existing `_crt_panel` renderer; add the
  letter-sort animation there, keep font `font_terminal_small`.

### 4.5 Audio

`src/missions/m6/m6_audio.py` (procedural):
- reuse: `m6_snow_step`, `m6_terminal_beep`, `m6_radio_static`,
  `m6_heli_away`, `m6_rotor_away`, `m6_wind_gust`, `m6_door_creak`;
- new one-shots: `m6_keyclick` (typing), `m6_switch_click`,
  `m6_heli_land` (rotor approach, rising), `m6_heli_door` (slide + slam);
- per-scene beds: add the three new scene ids to the bed table (L37-49);
  `m6_helicopter` bed fades from outside (loud) to cabin (muffled low-pass)
  to wide (distant) - drive with the existing per-cue volume.

### 4.6 Data and contract updates

- `src/missions/m6/meta.py`: new `mission6_ending_shots` list with the new
  ids, durations, cues; M6_FILM_SCENES picks them up automatically.
- `src/cutscenes/m6films.py`: register new renderers + fallbacks in
  `M6_3D_SCENES` and the `_take(...)` table; update the module docstring's
  scene list.
- `docs/MISSION6_PLOT.md`: update "Ending Cutscene Shot-List".
- Tests that pin the chain: `tests/unit/test_m6_campaign.py` (~L200, L272,
  L706, L789) and `tools/smoke_test.py` (~L8410). Update the expected lists;
  keep the radio-variant tests (variant detection by line text in
  `_radio_variant` still works, add the new silent shots).
- Goldens: `tools/ae_golden.py` - re-bless only the M6 ending shots; every
  other cutscene golden must stay byte-identical.

---

## 5. Order of work

1. A0 probe; confirm root cause and the screenshot's oval.
2. A1-A4 occlusion fix; render train + yard frames before/after.
3. A5 ground spills to pools.
4. B1-B8 halo redesign on the tuning sheet, then in scene. Perf check (A7).
5. Commit 1: "M6 3D: lights occlude, halos without rings".
6. C: E1, E2 (customs return + reveal) with fallbacks.
7. C: E3-E9 (radio sequence, silence, cut line) with fallbacks.
8. C: E10 helicopter H1-H3 with fallbacks; heli door anim, nav lights.
9. Audio, meta, docs, tests, goldens.
10. Commit 2: "M6 ending: the return, the reveal, the call, the pickup".

---

## 6. Verification

- **Occlusion:** probe frames from `tools/m6_shots.py` (train boxcar probe,
  yard) - every lamp behind a wall/carriage shows no halo; a guard walking
  past a lamp hides it per pixel; no billboard ovals on vertical surfaces.
  Compare against the playtest screenshot's camera position.
- **Look:** tuning sheet before/after; user sign-off on 3-4 frames.
- **Perf:** combat and canon cinematic mean within +0.5 ms of STATUS numbers
  (~18 / ~16.4 ms); no new hitch > 2x median.
- **Ending:** render a contact sheet of every ending shot at 4 times each
  (3D and forced 2D fallback with `ACARISTAN_CUTSCENE3D=0`), plus a full
  ending playthrough via `--dev` entry to the M6 ending.
- **Readability check:** show the contact sheet with no dialogue to someone
  (or the user) and ask the 11 beats in 4.1; each must be answerable.
- Gates: `python tools/smoke_test.py` (SMOKE TEST: OK),
  `python -m pytest tests/unit/test_m6_campaign.py`,
  `python tools/ae_golden.py verify --kinds cutscene` (only re-blessed M6
  ending shots differ), `python tools/ae_normalize.py`.

---

## 7. Risks

- Lights changing layer could reorder against other layer-6 effects (snow is
  layer 4 with no depth test, unaffected); sort order is kept, only the
  occlusion enc changes - low risk, verify with the probe.
- Partial occlusion cost in `_composite`; mitigated by A3 skip-first and A7.
- M5 shares `m5fx3d`'s `FX_LAYER` and `gl._composite`. The `light` tag is only
  set by `m6fx3d`, so M5 output stays identical; the cutscene goldens prove it.
- New ending scene ids touch a pinned contract; all pins are listed in 4.6.
- Ending length grows ~20 s; keep skip working per shot (CutscenePlayer).

---

## 8. Decisions for you (defaults chosen if you do not say)

1. **Halo style:** default = small hot core + smooth dithered falloff (no
   rings). Alternative: no halos at all on lamps, emissive heads + pools only.
2. **New ending shots:** default = add the 3 new scene ids (E1, E7, E9).
   Alternative: fold them into existing ids (keeps the contract, messier code).
3. **Maru on screen in the pickup:** default = yes, in the helicopter door
   (makes "Maru's helicopter" literal). Alternative: unseen pilot only.
4. **Ending length:** default ~58 s. Alternative: trim E5/E7 for ~50 s.
