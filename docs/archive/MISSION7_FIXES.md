# Mission 7 fixes

- Rebuilt Fallow 12 mesh: continuous shaped walnut stock, octagonal barrel and magazine tube, recessed muzzle, open trigger guard, ribbed pump and ejection-port detail.
- Matched shotgun hand anchors to the new furniture. Applied two-hand hold solving to moving poses as well as stationary poses; reduced exaggerated pump-arm movement.
- Fixed the tractor dismount softlock: Biribel now climbs down on clear ground rather than inside the pen fence or another character.
- Replaced the obstacle-crossing tractor route with a clear guided reversing route. Relocated the feed bin and well (both drawing and collision/interaction points), plus the prep-stage characters and bike, to keep the manoeuvring lane clear.
- Steering prompts wait for the player, accept held controls, support WASD/arrows, and no longer stall on a short timer. Travel duration scales with distance; turning stages remain guided stationary manoeuvres, not a free-driving vehicle simulation.
- Added baked field trees, post-and-rail fences, hay stacks, an old cart and foreground stubble around the intro landing field without obstructing the helicopter pad.

## Verification
- `python tools/smoke_test.py`: SMOKE TEST: OK.
- `python -m compileall -q src`: passed.
- `python tools/m7_route_probe.py`: passed, 808 sampled tractor poses tested against map solids, NPCs and bike; dismount collision-free.
- `python tools/engine3d_check.py`: OK, worst software/GL pixel difference 3.26%.
- Intro software-render frame rendered successfully and visually reviewed.
- Full `tools/ae_ci.py` did NOT pass: this archive lacks the API snapshot, and the aggregate run also reports unit-test, stale asset-bake, golden/replay, loop-parity, mission-0 and nested smoke failures. The standalone full smoke suite passed. These aggregate failures have not been resolved; this is not a claim of full CI certification.

The downloaded source ZIP was deleted immediately after extraction. The deliverable ZIP is a newly created archive of the updated project.

## Follow-up: 2D Alex handover
- Rebuilt the separate procedural 2D shotgun silhouette, including swept stock, compact receiver, open trigger guard, pump and parallel barrel/tube.
- Replaced oversized oval insert hands with shaped wrapped grips and cuffed forearms that extend out of frame.
- Insert and hands now share the exact same gun coordinate frame, eliminating cropped-prop alignment drift.
- Updated wide-shot grip spacing and Alex's support-hand target.
- Re-ran full standalone smoke suite: SMOKE TEST: OK; compileall passed.

## Follow-up: raid readability and presentation
- Alex now holds a selected firing lane for the current target instead of recalculating a flank every 2.5 seconds; his follow behavior has a wide dead zone and a slowly refreshed goal to avoid orbiting Biribel.
- Reworked the farm edge dressing with distant pasture strips, a visible north tree line, and three framed approach gates aligned to the orchard, north footpath, and south truck lane.
- Rebuilt the raid flame silhouette as irregular layered tongues, softened/reduced the smoke and glow, and moved barn flames to the facade's front plane. Raid fire uses world-depth sorting so allies and guards can cover it when in front.
- Rendered a review sheet at `previews/mission7_feedback_contact.png` plus four full-size shots in `previews/mission7/` (farm, approaches, fire, Alex).
