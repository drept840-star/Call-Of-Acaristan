# Mission 5 Visual Gauntlet - Nitpick Log

Global art conventions (all M5 sprites / 3D decals):
- **Light direction: key light from upper-left (-x, +y).** Highlights on top/left edges, shade on bottom/right.
- Palette: Acaristan desaturated - Guard red (150,30,28), cream paper (214,200,164), ink (28,24,22), brass (176,140,62).
- **All sprite / decor text is English** (user request, cycle 1). Romanian decor strings translated: FREE / MAG / TRUTH, FREE PRESS, NEVER FORGET, MAG PRINT WORKS, SAVE THE PRESS, NO, PROVOCATEURS.
- Sprites live in `src/art/m5/<asset>.py`, expose `render(variant=0, scale=1) -> pygame.Surface` (pygame only), are baked by `tools/bake_m5_sprites.py` into `assets/sprites/m5/` (26 files), and load through `src/art/m5/__init__.py:get()` (cached; baked PNG -> live `render()` -> None, caller keeps the legacy drawing as fallback).
- 3D cutscenes map sprites through `src/cutscenes/m5decal.py` (greedy-merged coplanar quads, depth-correct in GL and software backends).

Tools: `tools/m5_gauntlet_cycle.py` (full composite cutscene renders + burst strips + timing), `tools/m5_gauntlet_shots.py td` (gameplay shots), `tools/m5_view_export.py`, `tools/m5_draw_audit.py` (procedural draw-call census).

## Nitpicks

| ID | Cycle | Take/area | Frame | Problem | Severity | Skill lens | Fix | Status | Before -> after |
|---|---|---|---|---|---|---|---|---|---|
| N01 | 1 | end01 m5_ucilev_scope | 06133 | Scope readout hidden under dialogue box | S1 | UI/readability | Readout moved into 4 cached labels flanking reticle; reticle mask cached | VERIFIED | cycle_1 -> cycle_1_after2 end01 05111 |
| N02 | 1 | in02 m5_retardovici_tv | 05755 | Forearms/fists float detached from body | S1 | Anatomy/pose | Hands planted on lectern, eased gesture beats | VERIFIED | cycle_1 -> cycle_1_after in02 |
| N03 | 1 | in04 m5x_squadmate | 02800 | Squadmate arm passes through Biribel's chest | S1 | Staging/collision | `_SM_GAP_HELD` 0.74->0.84, clap targets top of shoulder | VERIFIED | cycle_1 -> cycle_1_after4 in04 03266 |
| N04 | 1 | in01/mid06/mid10 | many | Lamp halos show hard concentric bands | S2 | Lighting | `m5fx3d._halo_smooth` per-pixel falloff + Bayer dither | VERIFIED | cycle_1 -> cycle_1_after mid06 |
| N05 | 1 | mid04/mid00/mid01/mid10/mid15/in00 | various | Blank placeholder wall art (sign, posters, banner, portrait, map, crests) | S2 | Set dressing / sprite art | `src/art/m5/` sprites on decal meshes | VERIFIED | cycle_1 -> cycle_1_after3..5 mid04/mid06/mid00/in03/mid16/in02 |
| N06 | 1 | all non-continuable lines | - | "ANALYZING FILE..." prompt | S3 | UI | Game-wide convention (shared engine) | WONTFIX | |
| N07 | 1 | in05 m5x_change | 03000+ | Quartermaster holds a black slab as tunic | S2 | Props | `_held_vest`: collar, brass buttons, folded sleeves, armband, hem. Dip-to-black was a false alarm | VERIFIED | cycle_1 -> cycle_1_after5 in05 01066 |
| N08 | 1 | mid17/in01/mid11 | various | Wide skin band at nape | S2 | Character model | Shared rig: faded nape box for non-bald / non-hood styles | VERIFIED | cycle_1 -> cycle_1_after6 mid17 01266, in01 02400 |
| N09 | 1 | in01 m5_safehouse_tv | 02000 | "Flat blue bed" (actually TV screen-spill quad read as a rug); red/tan poster rect | S2 | Lighting / set dressing | Spill = 3 stepped floor-tinted rings; poster -> calendar decal | VERIFIED | cycle_1 -> cycle_1_after8 in01 02400 |
| N10 | 1 | in03 m5x_decree | 01500 | Foreground armband reads as floating red brick | S2 | Character model | Rig armband hugs sleeve (0.121x0.07x0.131), shaded edges | VERIFIED | cycle_1 -> cycle_1_after6 in03 00888 |
| N11 | 1 | mid11 m5x_maru_two | 02000 | Biribel's back blocks ~40% of frame | S2 | Composition | Camera (-3.2+0.3k,1.6,0.1) -> (0.3,1.3,0.2), fov 56 | VERIFIED | cycle_1 -> cycle_1_after5 mid11 01133 |
| N12 | 1 | mid00 m5x_faces_wide | 01000 | Sandu tangent to Biribel; blank red block; poster tangent to head | S2 | Composition | Camera (-4.2+0.25k,1.65,-5); kiosk posters decals pasted low (y 1.0) | VERIFIED | cycle_1 -> cycle_1_after7 mid00 00933 |
| N13 | 1 | mid04 m5x_pw_arrival_wide | 02000 | Red blob above door | S3 | Set dressing | guard_plate decal ("GUARD") | VERIFIED | cycle_1_after3 mid04 |
| N14 | 1 | mid17 m5x_breach | - | Caption begins with "[" | S3 | Writing/UI | Intentional stage-direction convention | WONTFIX | |
| N15 | 1 | mid11/mid16 print works | - | Paper stacks identical copies | S3 | Set dressing | Irregular heights/widths/tones, offset top bundles, lit tops | VERIFIED | cycle_3 mid16 00577 |
| N16 | 1 | in06 m5_river_gate | - | River-gate figure low detail | S3 | Character | Defer | OPEN | |
| G1 | 1 | gameplay quarter | g_quarter_* | Wall posters anonymous rects | S2 | Set dressing | decor_paint blits wall_posters v5/v6 | VERIFIED | td shots |
| G2 | 1 | gameplay print works | g_print_* | Bills font-drawn in Romanian | S2 | Sprite art / language | decor_interior `_poster` blits wall_posters sprites (English) | VERIFIED | g_print_raid "MAG 1991" / "FREE PRESS" |
| G3 | 1 | gameplay decor/tram/inspect | - | Romanian text in decor, tram, inspect art | S2 | Language | Translated to English (see conventions) | VERIFIED (decor, tram, all 6 inspect layers reviewed from bakes) | |
| G4 | 2 | inspect "paint" | static layer | "GUARD BLACK" label wider than the can label, first letter clipped | S2 | Typography | Label font 0.29r -> 0.24r, jitter +-0.28r -> +-0.1r | FIXED, VERIFIED in bake | inspect_art_3 |
| N17 | 2 | end04 m5_radio | 05866 | Vasile's office: empty gilt frame (two flat boxes) | S2 | Set dressing | portrait_frame decal (same as m5mid3d office) | VERIFIED | cycle_2 end04 05866 -> cycle_3 end04 |
| N18 | 2 | mid08/mid10 vasile close | 02266 | President portrait cropped by frame top | S3 | Composition | Acceptable: reads as the portrait above him; keep | WONTFIX | |
| N19 | 2 | mid04 pw_arrival_wide | 03000 | Biribel half out of frame at left | S3 | Composition | He is walking in; keep | WONTFIX | |

## SPRITE CONVERSION LIST

Source: `python tools/m5_draw_audit.py 8` (33 functions, 513 draw calls). Each item -> `src/art/m5/<asset>.py`.

| Asset | Replaces (procedural) | Draw calls | Status |
|---|---|---|---|
| posters (6 variants) | m5mid3d blank poster boxes / kiosk block | 8+ | DONE (decal, verified) |
| printworks_sign | m5mid3d `_street_set` sign loop | 9 | DONE |
| guard_banner / guard_plate | m5mid3d `_office_set` banner, door notice | 6 | DONE |
| district_map | m5mid3d `_office_set` map | 3 | DONE |
| portrait_frame | m5mid3d `_office_set` portrait | 3 | DONE |
| presidential_crest (seal, KRAP gear) | m5martial3d podium crest, depot crest | 6 | DONE |
| calendar / armband | safehouse poster rect, depot armband | 4 | DONE |
| wall_posters (7 variants) | decor_paint quarter rects, decor_interior font bills | 10+ | DONE (gameplay, verified) |
| hq_locker | draw._draw_hq_locker | 9 | DONE (verified g_hq_west) |
| mag (k9, 9mm) | draw._mag_sprite | 14 | DONE (baked; in-flight shot not captured) |
| tram_wreck | tram_wreck._wreck_sprite -> bake() blits baked PNG | 37 | DONE (verified g_quarter_mid/east) |
| m5_guard (3 kinds) | draw._draw_m5_guard -> sprite rotated into 64 cached headings; eyes, hit ring, helmet catchlight (screen-space upper-left) live | 20 | DONE (verified g_quarter_east) |
| maru (36 headings x 2 strobe) | draw._draw_maru_figure via _maru_pose | 16 | DONE (verified g_print_maru/raid) |
| mag_icon (2 kinds x 3 states) | draw._draw_m5_mag_icon shell; live round count overlaid | 9 | DONE (verified HUD in all td shots) |
| plate | draw._draw_m5_plate frame + bar well; title/fill/pips/readout live | 8 | DONE (verified convoy + raid plates) |
| press (run/alarm) / bale (4 sizes x label) | decor_interior _press / _bale (rnd stream preserved) | 18 | DONE (verified g_print_raid) |
| inspect_art (6 static layers) | inspect_fpv._static_for -> baked layer; *_dyn motion live | 80+ | DONE (bakes reviewed) |

All entries have the legacy drawing kept as fallback (sprite missing / size mismatch -> old code path). Bake: 125 files.

### Justified procedural (not converted)
- Rain streaks, sparks, muzzle/particle FX: per-frame animated, random.
- Light map / halos (`m5fx3d._halo_smooth`): runtime lighting from scene lights.
- Smoke motion: puffs move per frame.
- Stage floor/wall tiling in decor paint_*: baked once into the static layer per stage.

## Tests (latest run, cycle 1 close)
- `python -m compileall -q src tools`: rc=0
- `python tools/m5_fx_check.py`: M5 FX CHECK: OK
- `tools/engine3d_check.py`: worst pixel diff 3.99% -> OK (software 34.4 ms, gl 18.9 ms)
- `python tools/smoke_test.py`: SMOKE TEST: OK, mission5_sprites: OK - 26 sprites baked, loaded and meshed (check covers `check_mission5_sprites`: bake exists, bake == live render, get(), scale 2, decal face budget)
- `tools/bake_m5_sprites.py`: BAKE M5 SPRITES: OK (26 files)

## Cycle reports

### Cycle 1
- Renders: 27 scenes / 31 shots x 3 modes at 1000x700 with full UI composite; GL 31-85 ms/frame. Gameplay: 11 td shots.
- Found: 3 S1, 9 S2, 4 S3 (cutscenes) + 3 S2 (gameplay).
- Fixed + verified: N01-N05, N07-N13, G1-G3. WONTFIX: N06, N14. Open: N15, N16 (S3).
- Open S1/S2: none.
- Kill criteria NOT met at cycle 1 close: 7 sprite-conversion items open, no fresh cycle.

### Cycle 2
- Converted the 7 remaining sprite-list items (see list), smoke check extended (decal face budget for wall art, non-empty mask for gameplay sprites, call-site wiring for locker / guard / Maru). `SMOKE TEST: OK`, 125 sprites; compileall rc=0.
- Full re-render: 30 cutscene shots (GL) + 11 td gameplay shots, all reviewed.
- Found: 2 S2 (N17 empty frame in end04, G4 paint-can label overflow), 2 S3 kept (N18, N19). Fixed N17, G4, N15.
- Open S1/S2 after fixes: none. Because cycle 2 found new S2s, cycle 3 (fresh full pass) is required.

### Cycle 3 (fresh full pass)
- Full re-render: 30 cutscene shots (GL, frames at 35% - different moments from cycle 2's 60%) + 11 td gameplay shots, all reviewed.
- Verified: N15 (stacks varied), N17 (portrait in Vasile's radio office).
- New issues found: **none** (S1/S2/S3). Remaining open: N16 (S3, river-gate figure detail - deferred).
- Tests: SMOKE TEST: OK (mission5_sprites: 125 sprites baked, bake == live render, loaded, meshed/checked, call-site wiring); compileall rc=0; M5 FX CHECK: OK; engine3d_check worst diff 3.99% -> OK (software 28.7 ms, GL 15.6 ms).
- **Kill criteria: met.** Zero open S1/S2; every SPRITE CONVERSION LIST item converted, baked and wired with fallback; smoke sprite check passes; all tests pass; a fresh full cycle found no new issues.
