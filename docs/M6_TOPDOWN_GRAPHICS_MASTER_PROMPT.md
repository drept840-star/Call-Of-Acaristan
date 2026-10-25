# M6 top-down graphics - master prompt

Paste this into a fresh session, or load it in the current one. Written 2026-10-25 on branch `m6/train-polish`. Baseline frames rendered that day are in `shots/m6_master_prompt/`.

## Mission

The user's verdict: the top-down parts of Mission 6 (customs `customs`, no-man's-land `noman`, rail yard `rail`) look VERY bad next to the rest of the game. Make them look like they belong in the same game as the M4 street and the M5 quarter and HQ. Use graphify first, for every question about who draws what. Do not start by editing.

Done means: a side-by-side contact sheet of M5 reference frames and M6 frames where an outside viewer cannot tell the M6 frames come from a different art pass, and the user signs off on it. The user has not yet said which stage or element offends most, so rank them yourself in Phase 0.

## Hard rules (the user has rejected the opposite before)

1. House art only. Floors and walls come from the shared art pack (`artpack.tile` / `artpack.wall`, built by `tools/make_art_pack.py`). Hard-edged shapes, 1 px contact outlines, dark ambient with lamp pools. No soft alpha blobs, no speck or noise mottling, no lifted blue ambient. The user called exactly that "horrendous" and "blobby slop" on 2026-10-23 (memory: topdown-match-house-art).
2. No PS2 pipeline in the top-down game (no pixel-art, affine or dither filter). Decision log 2026-10-24 in `.wolf/cerebrum.md`. The 3D side keeps its PS2 look and stays untouched.
3. Characters keep the blocky box look (memory: keep-blocky-character-look). Polish lighting, props, ground; never the character models.
4. Do not touch: `train3d`, `yard3d`, `yard_*`, `bloc3d/`, `hud3d`, `cutscenes/m6*`, collision, the tile grids, spawn points, balance, exit-lock logic, voice, or the shared HUD plate.
5. Zero new per-frame cost beyond what is baked. Ground, walls and static props are baked once per stage (`decor._ground_surface`, `_prop_rows`); keep it that way. Per-frame additions after the light pass cost +1.1-1.4% before; stay under +2% in an interleaved A/B (`tools/m6_bench.py`; this PC swings 2x run to run, never compare two separate runs).
6. Art-pack changes may only ADD tile codes or sprites. Never change an existing tile's bytes: M3-M5 goldens depend on them.
7. The working tree is dirty with unrelated M3/M4/M6 work. Do not revert, stage or commit anything you did not write. Do not commit at all unless asked. Python edits written by script come out CRLF: normalize to LF (memory: python-edits-write-crlf).

## What I already know (verify before trusting)

Measured 2026-10-25 on 1000x700 frames, mean luma / near-black share / colour buckets:

| frame | mean | near-black | colours |
|---|---|---|---|
| M5 quarter_mid (golden) | 24.6 | 61% | 291 |
| M4 street (golden) | 29.5 | 28% | 112 |
| M6 customs_mid | 20.0 | 73% | 189 |
| M6 noman_mid | 30.7 | 28% | 180 |
| M6 rail_mid | 29.5 | 38% | 221 |

Brightness and colour count are comparable to M5. So "too dark" or "too blue" is NOT the root cause; do not fix this by tuning ambient first. The gap is structure and authorship. Leads, each to be confirmed by reading code and looking at frames:

- Only `customs` uses art-pack tiles: `decor.py:455-459` (`_house_tile` returns None for other stages) and `decor.py:567` (walls). `noman` and `rail` paint from `assets/tex3d` textures (the 3D set) tinted to near-grey through `_MATERIALS` (`decor.py:117`) and `_floor_material` (`decor.py:404`), then get `_ground_wear` blur mottle (`:420`) and a flat `_frost` wash (`:488`). Two different art sources inside one mission.
- M5's quarter is hand-authored: `paint_quarter` paints facades, windows, lamp posts, wet road and markings as a designed layer (`missions/m5/decor.py:111-135`). M6 is a generic grid bake (`_ground_surface`, `decor.py:1576`) plus scattered flat litter. It has no landmarks, no facades, no value hierarchy.
- Walls: `_paint_wall` (`decor.py:541`) and `_wall_drifts` (`:495`) repeat a scalloped snow cap per tile. In the frames it reads as a blue fringe on dark slabs, not as buildings or fences.
- Most props are code-drawn pygame shapes (over 20 `_draw_*` functions, `decor.py:1664-2137`); only vehicles, drums, crates and cable drums come from the pack (comment at `decor.py:1653`). Compare to the sprite pipeline (`tools/sprites/`).
- Ambient: customs (50,58,94) equals the M5 quarter; noman and rail are (92,105,140) and (95,106,136), `decor.py:64-70`. A smaller lead than the structure ones.
- Earlier passes (8820759, 57acb6c, 5ce2c44) already did floor variety, litter and exit plates. More of the same will not satisfy the user; the next pass has to be different in kind.

## Method

Graphify (the graph is `src/graphify-out/graph.json`; it uses an old node-ID scheme, so same-name files collide: use labels like `m6/decor.py` vs `m5/decor.py`, or `path::symbol`):

```bash
graphify query "<question>" --graph src/graphify-out/graph.json
graphify explain "m6/decor.py" --graph src/graphify-out/graph.json
graphify path "m6/draw.py" "m5/draw.py" --graph src/graphify-out/graph.json
graphify affected "<node>" --graph src/graphify-out/graph.json
```

Run `affected` on every function before changing it, and `graphify update src` before you finish. Use plain Grep/Read for exact strings.

Delegate mechanical work (renders, gate runs, sweeps, luma stats) to Haiku 5.5 subagents with exact commands, and spot-check their numbers. Keep design and code on the main model. Use the two-pass workflow: a creative plan pass first, then an implement pass.

### Phase 0 - baseline and diagnosis (no edits)

1. `python tools/m6_topdown_shots.py shots/m6_td_before --mid --guards --exit`
2. Look at every frame next to `tests/golden/baseline_v0/gp.m5.quarter_mid.png`, `gp.m5.quarter_start.png`, `gp.m5.hq_west.png`, `gp.m4.street.png`. Read `src/game/art/m5` and `missions/m5/decor.py` to see how M5 achieves its look.
3. Write a ranked defect list per stage. Each defect: what you see, the file and function that causes it, and a measurable property (luma spread, edge density, share of one repeated tile, count of distinct prop silhouettes).
4. Check `tools/sprites/palette.py` and `tools/make_art_pack.py` for the house palette and tile codes available.

### Phase 1 - art brief (creative pass, still no edits)

One short brief per stage: palette (house palette only), three value layers (ground / structures / lit pools), 3-5 landmarks that make the place readable at a glance (customs booth and barrier, the crossing strip and towers, the boxcar row and signal shack), what each lamp pool should reveal, what the walls should be (facades, fences, container walls) instead of repeated snow-capped slabs. Show the brief to the user before Phase 2 if it changes the look of a stage by more than polish.

### Phase 2 - one art source

Route `noman` and `rail` floors and walls through the art pack like `customs`. Add new pack codes (snow-dusted asphalt, ballast, gravel, yard concrete, container and fence walls) in `tools/make_art_pack.py`, rebuild, and confirm the M3-M5 tiles are byte-identical. Retire the blur mottle and the flat frost wash for those stages. Update `M6_TILE_BASE` (`decor.py:37`) if floor colours change, since the minimap samples it.

### Phase 3 - structures and props

Replace the weakest primitive-painted props and the per-tile snow-cap walls with authored, outlined art in the sprite pipeline (`tools/sprites/`, rebuild with `tools/build_all_sprites.py`). Give each stage its landmarks. Keep prop footprints identical to the grid: collision lives in `world.py` and every `B` tile is solid. Check `tall_drawables` and `hides` so tall props still hide the Guard IFF lamps.

### Phase 4 - light

Only after structure: compare lamp pools against M5 (`missions/m5/decor.py` `_light_pass`, `_torch_col`). Hard-edged blooms everywhere (`_hard_bloom`, as customs already does) instead of `_glow`. Solve Guard and cover readability with contrast and outlines, not with an ambient lift.

### Phase 5 - verify

```bash
python -m compileall -q src
python tools/smoke_test.py
python -m unittest tests.unit.test_m6_campaign -q
python tools/ae_golden.py verify --kinds gameplay
python tools/ae_api_snapshot.py   # only if a public engine API changed
python tools/m6_topdown_shots.py shots/m6_td_after --mid --guards --exit
```

Then build a before / after / M5-reference contact sheet, run the interleaved A/B perf check, and view every `after` frame yourself at full size. Known pre-existing reds (do not "fix"): `mission4_stage_transitions`, `mission4_cinematic_arrest`, `mission5_shadow_finale` geometry, `mission5_harbour_art` choreography, and on a clean HEAD `mission4_boot_and_walk` plus the M3 `02_interrogation_room` goldens.

### Phase 6 - wrap

Update `.wolf/STATUS.md`, `.wolf/cerebrum.md` (decision: one art source for the top-down game) and `docs/worklog.md`. Write the Obsidian session note under `Sessions/`. Refresh the code graph with `graphify update src`. Report what changed, what you did not verify, and the contact sheet path.

## Stop and ask the user when

- The brief for a stage changes its identity (layout feel, colour mood, landmarks).
- A fix needs a change to an existing art-pack tile, the grid, or a shared HUD element.
- Perf cost goes over +2% in the interleaved A/B.
- A gate that was green before your change goes red.
- You are about to add noise, blur or soft blobs to hide a flat area. That is the rejected approach; build a hard-edged shape instead.
