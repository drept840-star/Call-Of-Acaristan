# Mission 4 fix pass — "The Aftermath"

All six reported issues are fixed in `game_source_fixed.txt` (same concatenated
format / section order as the uploaded `game_source.txt`; it re-splits losslessly
into the module tree in `game/`). Before/after headless renders are in `shots/`.

## 1. Big building over-clustering the smaller ones (street map)
The radio-station monolith (`STATION_BLOCK`) was stamped over cols 31-38 / rows
14-22, which **overlapped** the `mid_29` block (its east column was swallowed)
and the `blvd_s_7` row (its top row was swallowed), and left it flush against
both - hence the clipped, clustered facades.

* `STATION_BLOCK` realigned to the street lattice: `(34, 14, 5, 7)`.
  The col-33 N-S lane now separates it from `mid_29` (restored to the full
  4-col band), the row-21 sidewalk separates it from the `blvd_s` row, and
  H-lane 14 from `blk_35b`. No footprint overlaps anywhere now.
* West door moved with it: `STATION_DOOR_TILE = (34, 19)`; foyer vestibule
  re-carved at `(35, 18, 3, 3)`.
* Monumental facade art re-anchored (satellite dish, mast, flagpoles, KRAPNET
  marquee) so the props stay on the narrower block.

## 2. Stages could be skipped
The street stage used to arm the door objective on *proximity* to the drop, and
the station door triggered on proximity too - sprinting past the cache skipped
the whole first beat.

* The cache is now a real pickup: `E` on the drop (`flow._take_cache`), with
  pickup sfx, floating text and a Vasile radio line.
* `_enter_station()` is gated on `STATE.m4_cache_taken`; touching the door
  without the cache just gets you a Vasile reminder.
* `check_mission4_stage_transitions` now asserts the gate (door first, then
  pickup, then door again).

## 3. Colliding text at the Maru meet
`_draw_m4_npcs` blitted each NPC's full role title as one centered line; Maru
and Vasile stand two tiles apart, so "MAG LIAISON / FORMER IPA ARCHIVIST" and
"KRAP FIELD COMMANDER" printed on top of each other (your screenshot).
Role lines are now word-wrapped to a 118 px column stacked above each name tag -
no overlap at any camera position.

## 4. "Grab idk what" - the drop was a generic crate
`_M4_FIXTURE_PROP` blitted `prop_crate` for the `V` tile. Replaced with a
bespoke sprite (`_m4_draw_cache_prop` / `_m4_cache_sprite`): olive hard case
with brass latches + corner irons, lid stencil, carry handle, a field
transceiver strapped on top with a coiled whip antenna, plus a live blinking
LED. It is drawn in a dynamic pass (not the static bake), so it disappears for
good once picked up, and the objective beacon stops pulsing on empty sidewalk.
Opening objective text now says what to do: "pick up the KRAP comms cache (E)".

## 5. Random enemy in the Maru/Vasile room
The station grid spawned a static loyalist guard (`E` at 15,5) inside the
transmitter hall - i.e. a hostile wandering through a friendly dialogue scene
(`HOSTILES: 1` during the meet). Removed. Loyalists now only exist via the
siege director once `STAGE_COMMIT` starts, committing through the assault
doors as intended.

## 6. The meet-room layout / doors to nowhere
* Dead-end door pockets are gone:
  * north assault door (15,8) opens into a real **stair anteroom**
    (cols 14-16, rows 9-11) whose south-east corner hands over to the studio
    wing - a second route, not a hole in the wall;
  * east assault door (11,13) mouths into a **utility spine** (cols 10-12,
    rows 10-12) that connects back up to the transmitter hall via (11,9) -
    a genuine second hall-to-hall corridor;
  * the street map's vestigial foyer corridor (a dead-end "L" stub behind the
    station door) was removed; the door now opens into a shallow vestibule.
* New interior dressing pass (`_draw_m4_station_dressing`, dynamic so it
  survives the street<->station swap): skirting trim wherever floor meets
  wall, engraved room plates (TRANSMITTER HALL / ENTRY HALL / STUDIO A /
  STAIRS / UTILITIES), and furniture that owns real collision rects
  (`world._build_station_world`): TX rack row with CRTs + LEDs along the north
  wall, console desk + chair, entry-hall bench, studio broadcast table with
  mics, utility shelving bays. Flat decals (cable coils, entry rug, torn
  posters, stair flight, lit ON AIR box) finish the rooms. Walkable lanes are
  preserved around every prop, and the siege insertion tiles stay walkable.

## Bonus bug found by the smoke test while verifying
`_spawn_loyalist_fireteam` could overshoot `M4_MAX_CONCURRENT`: a two-man team
committed at cap-1 alive made 7. The marksman add-on is now gated on the cap
(`check_mission4_hold_clock` asserts the cap every frame and passes).

## Verification
* Rebuilt the module tree from the concatenated source, installed pygame +
  numpy, ran the game's own headless suite:
  * all 7 `check_mission4_*` checks PASS (boot/walk, layout flood-fill,
    stage transitions incl. the new skip gate, checkpoint routes, hold clock,
    ending shots, campaign chain);
  * the full `missions.m3.main()` smoke suite passes except 3 pre-existing
    environment failures unrelated to these changes (the bundle never
    contained `mp_server.py` / `mp_join.py` / `assets/fonts/*.ttf`).
* Headless renders before/after: `shots/before_*.png` vs `shots/after_*.png`
  (street + station + meet room + entry hall) and `shots/after_siege.png`
  (siege running in the reworked rooms, concurrency within cap).
