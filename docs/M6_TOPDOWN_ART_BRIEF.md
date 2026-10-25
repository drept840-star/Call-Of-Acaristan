# M6 top-down art brief (Phase 0 diagnosis + Phase 1 brief)

Written 2026-10-25 on `m6/train-polish`. No code changed yet.
Frames: `shots/m6_td_before/` (contact sheet `contact_before.png`).
Metrics script: crop y 170..570 (HUD out), see the table legend below.

## Phase 0 - measurements

| frame | seam64 | p50 | spread | edges% | soft% | specks/10k | blue (B-R) |
|---|---|---|---|---|---|---|---|
| M5 quarter_mid | 2.6 | 22 | 42 | 4.9 | 28 | 120 | -15 |
| M5 quarter_start | 2.1 | 19 | 34 | 3.6 | 25 | 96 | -6 |
| M5 hq_west | 3.7 | 32 | 45 | 2.2 | 45 | 37 | -7 |
| M4 street | 0.6 | 25 | 29 | 11.9 | 27 | 222 | +4 |
| M6 customs_mid | 5.7 | 11 | 23 | 1.3 | 17 | 15 | +13 |
| M6 noman_mid | 1.4 | 24 | 34 | 1.3 | 50 | 23 | +17 |
| M6 rail_mid | 2.7 | 23 | 27 | 7.7 | 41 | 137 | +10 |
| M6 rail_frame | 1.1 | 19 | 30 | 1.6 | 40 | 28 | +16 |
| unlit customs_map | 16.9 | | | | | | |

- seam64: power at the 64 px period vs its neighbours (above ~3 = visible tile grid).
- edges%: px with |grad| > 24 (hard shape edges). soft%: px with |grad| 2..6 (ramps: glow, blur, wash).
- specks: px that differ from their 3x3 median by > 28 (crisp small accents).
- blue: mean B-R of mid-tones (luma 15..90).

Correction to the master prompt: luma and colour count match M5, but hue does not.
M6 mid-tones are 25-30 levels bluer than the M5 quarter. That is the full-screen
haze wash and the lifted ambient, not the palette.

## Ranked defects (all stages)

1. **Walls are tiles, not buildings.** `_paint_wall` (decor.py:541), `_paint_roofs` (:693),
   `_wall_drifts` (:495) paint every C/W tile alone. M4 paints each building as one
   object (`m4/draw.py::_draw_m4_buildings`: plate, cladding, windows, cornice, roof
   props, 1 px relief, hard drop shadow). The customs border is 148 copies of one
   art-pack wall tile. Measure: edges% 1.0-2.7 vs M5 3.6-4.9 and M4 10-12.
2. **Soft ramps everywhere, no value hierarchy.** soft% 40-50 on noman/rail vs 25-30 on
   M4/M5. Sources: `_ground_wear` blur (:420), `_frost` wash (:488), `_ao_band`
   gradients (:1519), alpha `_ice_sheet` / `_oil_stain` ellipses (:966, :1037),
   `_glow` blooms outside customs (:2324), the per-frame haze tint (:2449-2452), and
   the soft searchlight wedges (`stealth.py::_draw_beam`).
3. **Blue cast.** blue +10..+17 vs M5 -6..-17. Sources: `_AMBIENT` noman/rail
   (92,105,140)/(95,106,136) (:64), haze tint (38,54,82,20) every frame, frost alpha.
4. **No crisp accents.** specks 10-30 vs M5 96-120 and M4 190-220. M5 gets them from
   rhythm: lamp posts every 5 tiles, kerb stones, lane dashes, posters, bright
   leaflets, all axis-aligned (`m5/decor_paint.py::paint_quarter`). M6 litter is
   low-contrast ((58,62,68) on (46,50,56)) and randomly scattered (`_litter`, `_debris`).
5. **Two art sources.** Customs uses the art pack (`_house_tile` :455, :567); noman and
   rail use tinted `assets/tex3d` materials (`_MATERIALS` :117, `_floor_material` :404).
6. **Visible tile grid.** Customs maps its 198 road tiles to art-pack `L`, which has
   32 px joints: seam64 16.9 on the unlit map. Noman/rail show the tex3d seams by eye.
7. **Props sit as islands.** Each outdoor prop gets its own scalloped drift
   (`_prop_foot_snow` :1073) and the props are scattered, not arranged in rows. The
   prop silhouettes themselves (hedgehog, sandbags, boxcar, booth) read fine.
8. **Customs is too dark and flat.** p50 11, spread 23 vs M5 quarter 22 and 42.

## Stage ranking (worst first)

1. **No-man's-land.** Flat grey field with a visible grid, blue haze, soft wedges,
   props as islands, no structure at all (284 `g` tiles of nothing). Defects 1-7.
2. **Rail yard.** Boxcars and the platform already read well. The ground between
   them is flat grey with seams, the tracks are 2 px lines instead of track beds,
   and the blue haze is on. Defects 2-6.
3. **Customs.** Already house art, but too dark, the road is a tile grid, and the
   walls are a ring of identical slabs with no buildings. Defects 1, 4, 6, 8.

## Phase 1 - brief

### Shared method (house look = M4 blocks + M5 rhythm)
- **Ground:** art-pack floors only, at most two open-ground codes per stage. Broad
  variation comes from authored world-space features (road vs verge vs apron), never
  per-tile hash patches. Retire wear blur, frost wash and soft AO bands.
- **Structures as blocks:** a block list per stage (like `M4_BLOCKS`), painted as one
  object each: plate, cladding, one continuous hard snow cap, roof plant, 1 px
  relief, and a hard offset drop shadow (M5 `shadow()` idiom). The grid and
  collision stay exactly as they are; only the paint over C/W runs changes.
- **Rhythm:** lamps, fence posts, kerbs and tank traps sit at fixed intervals on
  the axis.
- **Accents:** small bright warm items (lit windows, signs, hazard plates, paper)
  at M5 density.
- **Snow:** long hard-edged drift bands along walls and fences, not one scallop per prop.
- **Light:** drop the haze tint. Noman/rail ambient goes to the quarter family
  (50,58,94). Hard blooms everywhere (`_hard_bloom`). Each lamp pool lands on a
  landmark.

Targets in the same crop: edges% >= 3.5, soft% <= 30, blue <= +4, spread >= 32,
specks >= 60, seam64 <= 3.

### Customs - "the post"
- Palette: tar road (art-pack `.`), concrete apron (`g`), sodium amber pools,
  Guard red/black on booths, hazard yellow.
- Values: dark road (p50 about 20), a mid-value apron, buildings as the darkest masses
  with lit windows, amber pools on the gate and booths.
- Landmarks: the north gate with its booms, stop line and a lit CUSTOMS plate; the
  two booths with lit windows; the west customs hall as one building (roof plant,
  door light spill); the east store as a corrugated shed; the parked Guard trucks.
- Walls: the outer ring becomes a perimeter fence (posts, mesh, razor wire, one
  continuous snow band). Inner C blocks become the hall and the shed.
- Road tiles map to `.` plus lane paint instead of `L` (the grid code stays `L`).

### No-man's-land - "the strip"
- Palette: snow-crust verges, one dark asphalt road down the middle, cold white
  tower pools, two amber gate pools.
- Values: dark verges with long hard drift bands, a mid-value road, hard tower pools.
- Landmarks: the N and S gates with booths and plates; the centre road with lane
  paint; four floodlight towers with visible lamp heads and hard pools; the two
  razor-wire belts as continuous lines; tank traps in aligned rows.
- Walls: the border is a concrete border wall with a continuous cap and a watch
  post every few tiles.
- New pack code: snow-crust ground (hard crust plates, no noise).

### Rail yard - "the freight yard"
- Palette: ballast grey-brown, yard gravel, rust boxcars, platform yellow edge,
  a warm signal shack, cold yard lamps.
- Values: dark track beds, mid gravel, boxcars as the big masses, amber platform
  lamps.
- Landmarks: three full-width track beds (ballast band, sleepers, two rails, painted
  in world space like the M5 tram rails); the platform and canopy (already good);
  the signal shack (warm); the water tower; Volkov's marked boxcar.
- Walls: the W band stays the platform building. The side C runs become a
  warehouse wall or fence.
- New pack codes: yard gravel, ballast.

## Open questions for the user (identity changes)
1. Customs border: concrete ring becomes a perimeter fence?
2. Noman/rail: drop the blue haze and ambient to the quarter's (50,58,94). The night
   gets darker and neutral, and the snow reads white under lamps only.
3. Is no-man's-land the right stage to do first?
