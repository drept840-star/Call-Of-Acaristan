# AUDIT T2 — Assets & Replays: Is the video pre-recorded or live-rendered?

ROLE: Terminal 2 (Asset & Replay Detective) — READ-ONLY investigation
DATE: 2026-09-26
WORKSPACE: `E:\Code\Call of Acaristan\First try`
OUTPUT: `docs/AUDIT_T2_ASSETS_AND_REPLAYS.md` (this file — no source code edited)

CONCLUSIVE ANSWER (up front): **The video capture system renders live game ticks from scratch. It does NOT read from saved video files, replay buffers, or saved game states.**

All `.mp4` files in the repo are **write-only outputs** of that live pipeline. No code path opens an `.mp4`/`.avi`/`.mov` for reading, no `.rec`/`.demo`/`.pkl`/`.npz` replay file exists, and `save_data.json` / `settings.json` are campaign-progress/config stores — never frame or input-tape inputs. The trailer renderers explicitly redirect saves to a temp dir so they cannot even consume real player progress.

---

## 1. Media / replay file scan

Method: `glob` for `**/*.mp4|avi|mov|rec|demo|pkl|npz|json|sav|dat`, plus `**/recordings|captures|replays|renders`, plus directory listings of root, `trailers/`, `_cut_frames/`, `gauntlet/`, `assets/`, `shots/`, `tools/*.py`, `src/**/*video*.py`.

### 1.1 Video files found — 4 total, all outputs

| File | Location | Role (verified) |
|---|---|---|
| `ko_phase5_preview.mp4` | repo root | OUTPUT of `render_ko_video.py:33-36` (`OUT = ... "ko_phase5_preview.mp4"`) |
| `trailers/trailer_60s.mp4` | `trailers/` | OUTPUT of `tools/render_trailer.py:636` / `render_trailer_v2.py:558` (final muxed master) |
| `trailers/trailer_60s_silent.mp4` | `trailers/` | INTERMEDIATE silent tape piped from live frames (`render_trailer.py:635,638,556-565`) before 1080p+music mux |
| `trailers/trailer_smoke.mp4` | `trailers/` | OUTPUT of `--smoke` fast check (`render_trailer.py:632-633,687-692`) |

No other video containers exist:

- `**/*.avi` → 0 hits
- `**/*.mov` → 0 hits
- `**/*.rec`, `**/*.demo`, `**/*.pkl`, `**/*.npz`, `**/*.sav`, `**/*.dat` → 0 hits each
- Directories named `recordings`, `captures`, `replays`, `renders` → 0 hits each
- `src/**/*video*.py` → 0 hits (there is no video-player module)

### 1.2 JSON files — none are replay tapes

Repo-level `**/*.json` hits (excluding `node_modules/`) are:

- `save_data.json` (+ `.bak`) — 3-slot campaign progress. Verified content is `{version, current_slot, slots[{slot, occupied, last_completed_mission, last_completed_label, total_time, updated_at, progress, stats, flags}]}`. Contains e.g. `"progress": "m1"`, `"flags": {"mission1_started": true}` — no per-tick inputs, no positions, no frame hashes. Owner: `src/core/save_system.py:11,58-83`.
- `settings.json` (+ `.bak`) — display/volume/crosshair/grain config (22 keys, see `settings.json:1-23`). Owner: `src/core/settings_store.py:16,58-81`.
- `docs/manifest.json` — static code census (`{file, bytes, lines, top_level_defs}` per `src/` file), not runtime data.
- `tools/golden.json` — golden-image regression signatures. `tools/golden.py:1-15` documents it as `40x28 grayscale quantised to 16 levels` for 3 stills (`archives/comms/cell`); `render_all()` re-renders via `gc.game_draw()` live and compares with 2% budget. It is a test oracle, not a replay input — the current frame is always freshly rendered, then compared.
- `tools/.build_settings.json`, `package.json`, `package-lock.json` — build/tooling config.

No JSON file contains an input log, keyframe list, entity snapshot stream, or encoded frames.

### 1.3 PNG / frame directories — all outputs, not inputs

- `trailers/*.png` (`trailer_60s_contact.png`, `trailer_smoke_contact.png`, `trailer_smoke_tour.png`, etc.) — stills saved alongside trailers.
- `_cut_frames/` (65 PNGs: `cur_*`, `rev_*`, `arch_*`, `*_check.png`) — headless probe evidence frames.
- `gauntlet/` (24 PNGs: `key_f*.png`, `sheet_*.png`, `compare_*.png`) — key-frame / sprite-sheet audit outputs.
- `prop_audit/`, `room_audit_shots/`, `prop_audit_shots/` — dozens of audit stills (`m2_layout.png`, `arch_stacks.png`, `ko_ground_floor.png`, …).
- `shots/` — gitignored scratch (`shots/` in `.gitignore:37`); glob `shots/*` returns nothing tracked.
- `assets/` — static game art/audio only: `art/*.png` (tiles/props/rain/hands), `fonts/*.ttf`, `bg.jpg`, `demon.mp3`, `sprites/*.png`. No video, no replay.
- `menu_theme.mp3` (repo root) — the **only** non-gameplay media input to the trailer, muxed as background music in a second ffmpeg pass (`render_trailer.py:699-705`, `render_trailer_v2.py:611-616`). It is audio bed, not gameplay footage.
- `First try.zip`, `node_modules/`, `.venv/` — excluded as packaging/dependencies, not referenced by game or trailer code.
- `.gitignore:24-29` explicitly treats `save_data.json`/`settings.json` (+`.bak`/`.tmp`) as **local runtime state**, and `shots/`, `probe/` as **local verification scratch** — consistent with outputs, not shipped replay assets.

No directory in the repo functions as a replay buffer or capture ingest folder.

---

## 2. Where (if anywhere) are video / replay files referenced?

### 2.1 Every `.mp4` reference is a write target — zero read paths

Grep `\.mp4|VideoCapture|get_reader|av\.open|moviepy|\.avi|\.mov|replay|playback|demo.*play|load.*replay` over `*.py` (44 hits reviewed):

- `render_ko_video.py:36` — `OUT = ... "ko_phase5_preview.mp4"` — destination only.
- `tools/render_trailer.py:16-17,627,632-633,635,706` — docstring usage lines + `--out default="trailer_60s.mp4"` + `TRAILERS / "trailer_smoke_silent.mp4"` etc. — all destinations.
- `tools/render_trailer_v2.py:12-13,553,556-558` — same, wrapper over `render_trailer`.
- All other hits for `replay|playback|move` are false positives: `Rect.move()` (`cutscenes/m3cell.py:122,144,198`, `missions/m1/draw.py:725`), `Player.move()` (`missions/m1/update.py:457`, `missions/m2/update.py:359`, `missions/m3/flow.py:665`), `slot.move(x,y)` UI toast, `audio ... playback`, and narrative comments (see §2.4).

Negative grep (both `src/` and `tools/`) for reader-side APIs returned **nothing**:

- `VideoCapture|VideoReader|imread.*mp4|open.*\.mp4|pickle|np\.load|npz|replay_buffer|recorded|demo_file` in `src/` → only the 2 narrative `pre-recorded` comments in `missions/m3/meta.py` (see §2.4), no code.
- Same pattern + `cv2\.|imageio.*read` in `tools/` → 0 hits.
- `ffmpeg.*-i.*mp4|VideoCapture|av\.open|moviepy|pygame\.movie|mixer\.music\.load.*mp4|imageio.*get_reader|imread.*\.mp4` repo-wide → 0 hits.
- No `import cv2`, no `imageio.get_reader`, no `av.open`, no `pygame.movie`, no `pickle.load` / `np.load` of gameplay data anywhere in `src/` or `tools/`.

The only ffmpeg `-i -` (stdin) invocations are **encoders**, not decoders:

- `render_ko_video.py:38-43`: `subprocess.Popen([FFMPEG, "-y", "-f", "rawvideo", ..., "-i", "-", "-an", "-c:v", "libx264", ..., OUT], stdin=PIPE)` + `feed()` at `:70-71` does `proc.stdin.write(pygame.image.tostring(surface, "RGB"))`.
- `tools/render_trailer.py:556-565` (`open_pipe`): identical rawvideo-encode pipe; `feed()` at `:96-97` writes `pygame.image.tobytes(config.screen, "RGB")`; `mux_1080p_with_music()` at `:568-581` takes the **just-written silent mp4** + `menu_theme.mp3` → 1080p master; `export_vertical()` at `:584-620` center-crops it. The mp4 is an input only to the project's own second-pass filter (scale/pad/mux), never gameplay source.
- `tools/render_trailer_v2.py:449-467,469-500` — same wrapper muxes (`mux_1080p_with_music`, `mux_1080p_trailer_mix` with bed/sfx/vo WAV stems per `docs/PLAN_3_AUDIO.md`).

Data flow is strictly one-directional: **game memory → surface bytes → ffmpeg stdin → mp4 file**. There is no arrow pointing back.

### 2.2 The frames are live `game_update` + `game_draw` ticks — with receipts

All three renderers step the real simulation at 60 ticks/s and feed every 2nd tick to a 30 fps pipe:

- `render_ko_video.py:219-242` (`tick()`): `gc.game_update(KEYS)` → `gc.game_draw(cam)` → `frame+=1; if frame%2==0: feed(screen)`. `capture()` at `:278-280` loops `ticks` times; `preroll_until_contact()` at `:265-272` advances **unfed** (`capture=False`) until the bot is firing so "the first captured frame is already shooting" — dead walking is discarded, not replayed. Scene log prints `fed ticks START-END (N ticks = Ns)`.
- `tools/render_trailer.py:447-470` (`run_gameplay`): `top_up()` → `router.step()` → `combat_pre()` → `gc.game_update(KEYS)` → `combat_post()` → `gc.game_draw(cam)` → `_apply_muzzle_flash()` → `FRAME+=1; if FRAME%2==0: feed()`. `run_walk()` at `:473-488` does the same via `ws.update_walking_sim` / `ws.draw_walking_sim`. Each `SECTIONS` entry (`:545-553`) calls a real starter (`gc.start_mission`, `start_mission2`, `start_mission2_sniper`, `start_mission3_*_checkpoint`) followed by a 60-tick pre-roll (`:667-672`) "so first fed frame is mid-action, never spawn idle".
- `tools/render_trailer_v2.py:333-360` (`run_gameplay` wrapper) + `:272-312` (`_run_melee_rush`): same tick loop plus trailer-only presentation (impact shake, grain, top bug tag). Bottom caption pill explicitly **removed** (`caption()` at `:220-225` is a no-op: "bottom of screen must stay completely clean").
- Facade `src/core/game_core.py:167-180` proves `game_update`/`game_draw` route to the live mission sims (`m1`/`m2`/`m3.game_update/draw` based on `STATE.active_mission`), not to any file player.

Inputs are **synthesised live**, not played back:

- `render_ko_video.py:87-153` (`Router` + A* via `entities.enemy_ai._astar`), `:169-197` (`combat()` aims with velocity lead, calls real `weapons.handle_shoot()`/`handle_melee()`), `:200-216` (`seek_cover()` reads live overwatch telegraph).
- `tools/render_trailer.py:340-426` (same `Router` + jitter recovery), `:288-319` (`combat_pre/post` with LOS check via `weapons._wall_blocks_line`, lead pursuit, burst gating).
- `src/tools/trailer_bot.py:1-201` — "deterministic operator driver for cinematic capture ... the bot does NOT pathfind [it follows] waypoint lists ... Fires through the real weapons pipeline so shake/kick/casings/tracers match human play" (`:9-13,121-162`). Hooked into the live loop: `src/app.py:1242-1252` (`--trailer-bot` flag → `_bot.reset(act)`) and `src/app.py:2168-2179` (`keys_eff, _ = _bot.tick_bot(keys_eff)` immediately before `gc.game_update(keys_eff)`).

Title cards, boot typewriter, broadcast banner, and end cards are procedurally drawn `pygame.Surface` frames fed through the same pipe (`render_ko_video.py:74-84`, `render_trailer.py:100-220`), not composited from video clips.

### 2.3 Save files are campaign progress — and trailers deliberately ignore them

`src/core/save_system.py:1-213` owns `SAVE_FILE = <root>/save_data.json`; schema is slot progress/labels/flags/stats only (see §1.2). It records coarse segments (`walk`/`m1`, mission-complete records) for Continue/New-Game UI (`src/app.py:618,741,1513-1597`).

Crucially, the video pipeline **refuses to consume** real saves:

- `tools/render_trailer.py:37-40`: `_sv.SAVE_FILE = <tmp>/save_data.json`, `_st.SAVE_FILE = <tmp>/settings.json` — "headless real gameplay" against an isolated temp store.
- `tools/smoke_test.py:19-27` documents the same pattern: "mission-start progress writes never touch the real save_data.json/settings.json".
- Identical redirection in `tools/cursor_arrow_shots.py:101-105`, `tools/slot_select_shot.py:42-46`.
- Staging helpers that set mission flags directly (`render_ko_video.py:250-262 `stage_breakout_flags``, `render_trailer_v2.py:157-173 `stage_breakout``) exist precisely because "the trailer bot can't craft (drag-minigame), so without staging the cell door stays shut" — i.e. they film a later take by driving the live sim into that state, not by loading a save or replay.

### 2.4 The only "pre-recorded" strings are in-story fiction, not video assets

- `src/missions/m3/meta.py:302-304`: "The monitor snaps on AGAIN — Balaceanu's looped tape continues ... the next segment of the same pre-recorded address."
- `src/missions/m3/meta.py:330-331`: "Balaceanu reads the silence / defiance the same way — he's pre-recorded, he can't actually hear Biribel. That's the point, and the joke."

Both are cutscene dialogue comments: the villain's in-world broadcast is diegetically a tape. No file, decoder, or playback call backs them — the lines are rendered by the live cutscene engine (`cutscenes/engine.py`, `missions/m3/flow.py:375` "don't replay" a finished breach is a checkpoint flag, `core/state.py:184` "instead of replaying the intro ... cutscenes" is a skip flag).

---

## 3. Verdict

**Is the video capture system reading from saved files, or rendering live game ticks from scratch?**

**Rendering live game ticks from scratch — conclusively.**

Evidence chain:

1. Exhaustive extension/directory scan finds no replay-format files and no ingest directories; the only 4 mp4s are documented outputs of the three renderer entry points.
2. Every mp4 reference in code is a write destination; reader-side APIs (`VideoCapture`, `get_reader`, `av.open`, `moviepy`, `pygame.movie`, `cv2`, `pickle`/`np.load` replay) have zero references.
3. The pipe direction is provably memory→encoder: `game_update` → `game_draw` → `pygame.image.tobytes/tostring` → `ffmpeg rawvideo stdin` → `libx264 mp4`, at 60 ticks in / 30 frames out, with unfed pre-rolls and printed fed-tick ranges.
4. Bot inputs (`Router`, `trailer_bot.tick_bot`, `combat_pre/post`) call the real weapons/AI/movement code each tick; title/boot/end cards are freshly drawn surfaces.
5. Saves are progress flags, and renderers sandbox them to temp dirs; `golden.json` is a still-image test oracle re-rendered live, not a tape.
6. "Pre-recorded" hits are narrative (Balaceanu's in-fiction address), not technical.

What would falsify this: a `cv2.VideoCapture` / `imageio.get_reader` / `ffmpeg -i <mp4>` decode path feeding `game_draw`, a `.rec`/`.demo`/`.pkl`/`.npz` loader driving `KEYS`, or an mp4 opened in `rb` mode anywhere outside the mux second pass. None exists as of this audit.

---

### Investigator notes (repro)

- Re-ran greps over `src/**/*.py` and `tools/*.py` for reader APIs — clean (see §2.1 patterns).
- Key files read (read-only): `render_ko_video.py` (324 lines), `tools/render_trailer.py` (711 lines), `tools/render_trailer_v2.py` (626 lines), `src/tools/trailer_bot.py` (201 lines), `src/core/game_core.py` (254 lines), `src/core/save_system.py` (213 lines), `tools/golden.py` (125 lines), `tools/render_previews.py` (111 lines), `save_data.json`, `settings.json`, `docs/manifest.json`, `.gitignore`, plus `src/app.py:1240-1252,2168-2185` and `src/missions/m3/meta.py:295-339`.
- No source files created, edited, or executed; this report is the sole write (`docs/AUDIT_T2_ASSETS_AND_REPLAYS.md`).
