# AUDIT T1 — Capture Pipeline (Video Recording / Rendering / Frame Capture)

> ROLE: Terminal 1 (Capture Pipeline Auditor) — READ-ONLY investigation.
> Date (UTC): 2026-09-26
> Scope: entire repo. No source files were edited.
> Method: repo-wide `grep` for `ffmpeg`, `rawvideo`, `cv2`, `VideoWriter`, `moviepy`, `pygame.image.save`, `subprocess.Popen` (+ follow-ups: `imageio`, `libx264`, `yuv420p`, `faststart`, `\.mp4`, `tobytes`/`tostring`/`stdin\.write`, `ffprobe`), plus manual reads of every hit and of `tools/`, `src/tools/`, `trailers/`, `_cut_frames/`, `gauntlet/`, `pyproject.toml`, `build.bat`.

## TL;DR

- `render_ko_video.py` is **NOT** the only capture script. There are **3 video-capable Python entry points** (1 standalone + 1 primary pipeline + 1 wrapper that owns mux/slice paths), plus **1 manual ffmpeg recipe** in docs and **1 bot-driver feeder** that is often mistaken for a recorder.
- No `cv2` / `VideoWriter` / `VideoCapture` / `moviepy` / `av.open` / `mediapy` / `opencv` anywhere in first-party code. The only video encoders are **ffmpeg via `subprocess.Popen` rawvideo pipe** (2 flavours: `imageio_ffmpeg` binary vs system `ffmpeg`).
- Everything else matching `pygame.image.save` (≈16 scripts) is **stills-only** (PNG contact sheets / audits / probes). They cannot generate, slice, or export video on their own.
- `tools/dev_panel.py:604` (`subprocess.Popen`) is a **false positive**: it launches game instances, not ffmpeg.

---

## 1. Grep coverage (repro)

| Pattern | Hits (first-party, excl. `node_modules/`) | Verdict |
|---|---|---|
| `ffmpeg` | `render_ko_video.py:23,33,38-43`, `tools/render_trailer.py:55-60,557-562,568-581,589-613`, `tools/render_trailer_v2.py:401-402,449-466,477-500`, `docs/PLAN_3_AUDIO.md:46,114-123` | All real video paths found |
| `rawvideo` | `render_ko_video.py:39`, `tools/render_trailer.py:11,558` (reused by v2 via `rt.open_pipe`) | Confirms pipe protocol |
| `cv2` / `VideoWriter` / `VideoCapture` / `moviepy` / `opencv` / `imageio` (except `imageio_ffmpeg`) / `av.open` / `mediapy` | `render_ko_video.py:23` (`imageio_ffmpeg` import only); zero hits elsewhere in `src/`, `tools/` | **Absent** — no OpenCV/moviepy pipeline exists |
| `pygame.image.save` | 16 scripts under `tools/` (see §4) | Stills only |
| `subprocess.Popen` | `render_ko_video.py:38`, `tools/render_trailer.py:557`, `tools/dev_panel.py:604` | First two = video; third = game launcher (false positive, §3.5) |
| `\.mp4` | `render_ko_video.py:36`, `tools/render_trailer.py:16-17,627,632-635,706`, `tools/render_trailer_v2.py:12-13,553,556-558`, `docs/PLAN_3_AUDIO.md:5,114,123`, `docs/worklog.md:229` | Outputs inventory |
| `stdin\.write` + `tobytes`/`tostring` | `render_ko_video.py:71` (`pygame.image.tostring(surface,"RGB")` → `proc.stdin.write`), `tools/render_trailer.py:97` (`pygame.image.tobytes(config.screen,"RGB")` → `PROC[0].stdin.write`) | The two live-frame pipes |
| `ffprobe` | `tools/render_trailer_v2.py:400-410` only | Duration probe for mux fade math |

`pyproject.toml:1-9` declares only `numpy`, `pygame-ce`, `setuptools` — `imageio_ffmpeg` is **undeclared** (works only if pre-installed in the environment). `uv.lock` contains no `moviepy`/`opencv` entries. `build.bat:1-22` is PyInstaller packaging only (no video).

---

## 2. Scripts capable of generating / slicing / exporting video

### 2.1 `render_ko_video.py` — standalone headless KO preview (video GENERATOR)

- **Path:** `render_ko_video.py:1-324`
- **Pipe:** `render_ko_video.py:33` (`FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()`), `render_ko_video.py:38-43` (`subprocess.Popen([FFMPEG, "-y", "-f", "rawvideo", "-vcodec", "rawvideo", "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", "30", "-i", "-", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", OUT], stdin=PIPE)`)
- **What it takes as INPUT:** **Live game loop** (headless real gameplay). Not recorded frames, not pre-existing clips:
  - Boots with `SDL_VIDEODRIVER=dummy` / `SDL_AUDIODRIVER=dummy` (`render_ko_video.py:15-16`), `sys.path → src/`.
  - Drives `core.game_core.game_update(KEYS)` + `game_draw(cam)` at **60 ticks/s**, feeds **every 2nd tick** to get 30 fps (`tick()` at `render_ko_video.py:219-242`, `frame[0] % 2 == 0 → feed(screen)`).
  - Own bot logic in-file: `Router` (A* via `entities.enemy_ai._astar`, `render_ko_video.py:87-153`), `combat()` with target-leading + `weapons.handle_shoot()`/`handle_melee()` (`render_ko_video.py:169-198`), `seek_cover()` for overwatch lanes (`render_ko_video.py:200-216`), `preroll_until_contact()` advances UNFED until firing (`render_ko_video.py:265-272`) so first fed frame is already combat.
  - Timeline (`render_ko_video.py:282-320`): Scene A M1 warehouse (`gc.start_mission()` + `missions.m1.map.mission1_map`, 360 ticks) → card → Scene B M3 breakout (`gc.start_mission3_breakout_checkpoint()` + staged shiv flags, 360 ticks) → card → Scene C M3 kill-order (`gc.start_mission3_kill_order_checkpoint()`, 420 ticks) → outro card. Cards are synthetic `pygame.Surface` fills (`card()`, `render_ko_video.py:74-84`).
  - Per-tick `feed()` = `pygame.image.tostring(surface, "RGB")` → ffmpeg stdin (`render_ko_video.py:70-71`).
- **What it OUTPUTS:** silent MP4 `ko_phase5_preview.mp4` at repo root (or `$ARENA_WORKSPACE/`, `render_ko_video.py:34-36`), native `WIDTHxHEIGHT` @30fps, `libx264`, `yuv420p`, `crf 20`, `+faststart`. No audio (`-an`). Verified artifact exists at repo root (`ko_phase5_preview.mp4`). Corroborated by `docs/MISSION3_KILL_ORDER.md:284` and `docs/worklog.md:229` ("60 ticks/s → 30 fps MP4").
- **Slicing:** no post-slice; preroll ticks are dropped pre-feed (dead-time kill), not a file slice.

### 2.2 `tools/render_trailer.py` — primary trailer pipeline (video GENERATOR + SLICER/EXPORTER)

- **Path:** `tools/render_trailer.py:1-711` (header `tools/render_trailer.py:1-19`)
- **Pipe + mux:** `tools/render_trailer.py:54-60` (FFMPEG = `shutil.which("ffmpeg") or C:\ffmpeg\bin\ffmpeg.exe`; hard-fails if missing), `open_pipe()` at `tools/render_trailer.py:556-565` (`subprocess.Popen([FFMPEG, "-y", "-f", "rawvideo", ..., "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", FPS(30), "-i", "-", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", "-movflags", "+faststart", out_path])`), `feed()` at `tools/render_trailer.py:96-97` (`pygame.image.tobytes(config.screen,"RGB")` → `PROC[0].stdin.write`).
- **What it takes as INPUT:** **Live game loop + synthetic cards + pre-existing audio file** (three input classes in one script):
  1. **Live gameplay (primary):** `SECTIONS` at `tools/render_trailer.py:545-553` (`m1`/`m2`/`m2sniper`/`m3break`/`m3comms`/`m3arch`/`m3ko` via `gc.start_mission*`), each with 60-tick (5 in `--smoke`) unfed pre-roll (`tools/render_trailer.py:666-672`) then `run_gameplay()` with Router/combat bot (`tools/render_trailer.py:653-678`). Also `run_walk()` (`missions.walking_sim`) and `run_menu()` paths exist. 60 ticks/s → feed every 2nd → 30 fps, native 1000×700.
  2. **Synthetic surfaces (generated in-script, not clips):** `boot_intro()`, `broadcast_card()`, `card()`, `black_frame()`, `end_card()` draw on `pygame.Surface` and `feed()` each frame — these are rendered, not read from disk.
  3. **Pre-existing audio clip (mux stage only):** `menu_theme.mp3` at repo root (`tools/render_trailer.py:699`). `mux_1080p_with_music()` (`tools/render_trailer.py:568-581`) runs a **second ffmpeg pass**: scale/pad native → 1920×1080 + mux music (`-c:a aac -b:a 160k -shortest`). `export_vertical()` (`tools/render_trailer.py:584-620`) center-crops to **608×1080 9:16** (`crop=608:1080`) for Shorts/TikTok — this is the in-repo **video slicer**.
- **What it OUTPUTS:** `trailers/trailer_60s_silent.mp4` (intermediate) → `trailers/trailer_60s.mp4` (default `--out`, `tools/render_trailer.py:627-636,704-706`), `trailers/trailer_60s_vertical.mp4` (optional, non-fatal), `--smoke` → `trailers/trailer_smoke.mp4` (~15 s, silent replaced, no mux, `tools/render_trailer.py:687-692`), `--no-audio` ships silent (`tools/render_trailer.py:694-697`). Artifacts present: `trailers/trailer_60s.mp4`, `trailers/trailer_60s_silent.mp4`, `trailers/trailer_smoke.mp4`.
- **CLI:** `python tools/render_trailer.py [--smoke] [--no-audio] [--out NAME]` (`tools/render_trailer.py:623-628`).

### 2.3 `tools/render_trailer_v2.py` — cinematic finish wrapper (video EXPORTER / SLICER, reuses v1 pipe)

- **Path:** `tools/render_trailer_v2.py:1-626` (header `tools/render_trailer_v2.py:1-15` explains split: Longcat owns `SECTIONS`/tours/`main()` loop; this file owns presentation + pacing).
- **Mechanism:** `tools/render_trailer_v2.py:22` (`import render_trailer as rt`), then monkeypatches `rt.card`, `rt.make_router`, `rt.run_gameplay`, `rt.run_menu`, `rt.run_walk`, `rt.mux_1080p_with_music` (`tools/render_trailer_v2.py:533-539`). It does **not** open its own rawvideo pipe — it calls `rt.open_pipe()` (`tools/render_trailer_v2.py:559`) and `rt.feed()` via its own `run_gameplay`/`run_menu`/`run_walk` (`tools/render_trailer_v2.py:315-393`, each ends `if FRAME % 2 == 0: rt.feed()`), adding grade/shake/`bug_tag` finish per fed frame.
- **What it takes as INPUT:** same two classes as v2 **plus pre-existing multi-stem audio**:
  1. **Live game loop** (via `rt.gc.start_mission*` + patched routers/tours at `tools/render_trailer_v2.py:517-528`; editor EDL takes at `tools/render_trailer_v2.py:48-93` reference `m2sniper`/`m1`/`m2`/`m3break`/`m3arch`/`m3ko`/`m3comms` starters).
  2. **Pre-existing audio:** `mux_1080p_with_music()` blur-pad variant (`tools/render_trailer_v2.py:445-466`: split/scale/boxblur/overlay to 1920×1080 + `afade` in 2 s / out 4 s, `volume=0.8`, AAC 160 k) taking `menu_theme.mp3`; **and** `mux_1080p_trailer_mix()` (`tools/render_trailer_v2.py:469-500`, PLAN_3_AUDIO §5) taking **three pre-existing WAV stems** (`bed_wav`, `sfx_wav`, `vo_wav`) with sidechain duck + `loudnorm=I=-14:TP=-2:LRA=11`.
  3. **Pre-existing video for slicing/measurement:** `_probe_duration()` (`tools/render_trailer_v2.py:396-411`) shells to `ffprobe` (derived from ffmpeg path) to read `format=duration` off the silent MP4 — the only `ffprobe` use in the repo.
- **What it OUTPUTS:** same filenames as v1 (`trailers/trailer_60s.mp4` / `trailers/trailer_smoke.mp4`, `tools/render_trailer_v2.py:553-558,604-617`). Default (no `ACARISTAN_EDITOR_CUT`) delegates to `rt.main()` (`tools/render_trailer_v2.py:620-626`); with `ACARISTAN_EDITOR_CUT=1` runs `editor_main()` 58 s locked EDL (`tools/render_trailer_v2.py:541-617`, asserts `editor_runtime() ≈ 58.0`).
- **Classification:** capable of **generating** (via reused pipe), **slicing** (blur-pad scale/crop, `-shortest`/`atrim`, EDL sub-cuts), and **exporting** (final mux) video. Must be counted — it is not "just a filter."

### 2.4 Manual / documented pipeline (not a script, but slices/exports video)

- **Path:** `docs/PLAN_3_AUDIO.md:114-123` (exact `ffmpeg` command), gated by `docs/PLAN_3_AUDIO.md:5` (`trailers/trailer_60s.mp4` = 63.8 s, 1920×1080, AAC 160 k, −14 LUFS).
- **INPUT:** **pre-existing video clip + pre-existing audio clips** — `trailer_60s_silent.mp4` + `bed.wav` + `sfx.wav` + `vo.wav` (stems carry the M-SILENCE bass cut baked in).
- **OUTPUT:** `trailers/trailer_60s.mp4` (`-c:v libx264 -crf 17 -preset medium -c:a aac -b:a 160k -shortest -movflags +faststart`, blur-pad `scale=-2:1080` + overlay + `yuv420p`).
- **Note:** this is the offline recipe that `render_trailer_v2.mux_1080p_trailer_mix` automates. Included so a future "where did the trailer mix come from?" search lands here.

---

## 3. Related but NOT video-capable (do not count as recorders)

### 3.1 `src/tools/trailer_bot.py` — bot driver / feeder (no ffmpeg, no file out)

- **Path:** `src/tools/trailer_bot.py:1-201`. Zero `Popen`/`ffmpeg`/`tobytes` hits.
- **INPUT:** live game state (`STATE.player`, `NOTEBOOK_POS`/`EXFIL_POS`, per-act waypoint scripts `act1`/`act2_killbox`/`act2_evidence`/`act3_breakout`/`act3_relay`, `src/tools/trailer_bot.py:57-106`).
- **OUTPUT:** movement keys (`_FakeKeys`) + aim snap + `weapons.handle_shoot()/handle_throw_bottle()/handle_melee()/start_reload()/switch_weapon()` + `game_core.handle_interact()` per tick (`tick_bot()`, `src/tools/trailer_bot.py:121-162`). No frames or files written.
- **Role:** deterministic operator **consumed by** the capture pipeline (`acaristan.py --jump … --trailer-bot --trailer-act …`, per `docs/PLAN_1_CHOREOGRAPHY.md:25-27,275-298`). Listed here to prevent mis-classification.

### 3.2 `tools/dev_panel.py:604` — `subprocess.Popen` false positive

- **Path:** `tools/dev_panel.py:601-611`. `Popen(build_launch_cmd(target, …), cwd=ROOT)` launches **game instances** (dev jumps), appends to `self._procs` for terminate/reap. No ffmpeg args, no pipe, no video.

### 3.3 `src/audio/audio.py:33` — `tobytes` false positive

- Audio sample buffer serialization (`buf.write(samples.tobytes())`), not frames.

### 3.4 `tools/bench_frame.py`, `tools/audio_parade.py`, `src/tools/ko_playability_audit.py`, `tools/probe_holdout*.py`, `tools/probe_ko_behavior.py`, `tools/probe_stair_gap.py`, `tools/m3_*regression.py`, `tools/m3_*audit.py`, `tools/golden.py`, `tools/smoke_test.py`, `tools/build_code_pdf.py`

- Headless sim / benchmark / audit / census harnesses. They call `game_update`/`game_draw` but never pipe or save frames to video (verified by absence of `Popen`/`ffmpeg`/`tobytes`/`image.save` for video purposes; `golden.py`/`smoke_test.py` assert pixels, don't export).

---

## 4. Frame-capture (stills-only) inventory — explicitly NOT video

All use `pygame.image.save(surface, *.png)` on a **single live-rendered frame or synthetic surface**. Input is either one tick of the live game loop or a procedurally drawn sheet; output is PNG(s) only. None shells to ffmpeg, none writes `.mp4`/`.avi`, none sequences frames into a container. Grouped so T2–T8 don't re-audit them as "recorders":

| Script | Input (live frame vs synthetic) | Output dir |
|---|---|---|
| `tools/slot_select_shot.py:109` | live menu frame | `tools/shots/slot_select_*.png` |
| `tools/render_walk_rain.py:19-35` | live walking-sim (45 ticks) | `previews/walk_rain_*.png` |
| `tools/render_previews.py:34-36` | live `game_draw` ×5 scenes + menu | `previews/*_new|legacy.png` |
| `tools/render_ko_shots.py:25-29` | synthetic cutscene draws (`cutscenes.m3ko._draw_ko_*`) | `tools/shots/ko_*_*.png` |
| `tools/probe_ko_cutscene.py:44-62` | synthetic cutscene + vignette/scanlines/letterbox/dialogue | `_cut_frames/<tag>_*.png` (65 files on disk) |
| `tools/collision_map_audit.py:269-270` | live map + colour overlay | `prop_audit/collide_*.png` |
| `tools/collision_overlay_shots.py:63` | live `config.screen` | `*_col_*.png` |
| `tools/m3_room_shots.py:55,73` | live room draws + contact sheet | `room_audit_shots/*.png` |
| `tools/m2_walk_shots.py:35,47` | live M2 frames | `prop_audit/m2_*.png`, `walk_*.png` |
| `tools/m2_floor_shots.py:57` | live M2 floor probe | `prop_audit/probe_*.png` |
| `tools/prop_showcase.py:81` | synthetic prop combo surface | `prop_audit/props_*.png` |
| `tools/prop_audit_overview.py:99,117` | live map downsized | `prop_audit/full_*.png`, `walls_*.png` |
| `tools/cursor_arrow_shots.py:278,369` | synthetic cursor states | `tools/shots/cursor_*.png`, `_arrow_*.png` |
| `tools/compose_sheets.py:60,90` | **pre-existing PNGs** (reads `previews/*_{legacy,new}.png`, writes contact sheets) | `preview_world_before_after.png`, `preview_cinematics_ui.png` |
| `tools/make_art_pack.py:92` | synthetic painted sprites | `assets/art/*.png` |
| `tools/make_station_sprites.py:142` | synthetic pixel art | `assets/sprites/station_*.png` |

`compose_sheets.py` is the closest to "slicing" (it composites pre-existing images) but operates **PNG→PNG**, never video. `_cut_frames/`, `gauntlet/*.png`, `shots/`, `prop_audit/`, `room_audit_shots/`, `trailers/*.png` are artifacts of the above, not video sources.

---

## 5. Artifact map (disk state at audit time)

- `ko_phase5_preview.mp4` (repo root) ← `render_ko_video.py`
- `trailers/trailer_60s.mp4`, `trailers/trailer_60s_silent.mp4`, `trailers/trailer_smoke.mp4` ← `render_trailer.py` / `render_trailer_v2.py`
- `trailers/trailer_60s_contact.png`, `trailers/trailer_smoke_contact.png`, `trailers/trailer_smoke_tour.png` ← stills pipeline (not video inputs)
- `menu_theme.mp3` (repo root) ← mux input for both trailer renderers
- No `.avi`, no `*_vertical.mp4` on disk (export path exists but artifact not present), no `bed.wav`/`sfx.wav`/`vo.wav` stems on disk (recipe only).

---

## 6. Answers to the three mission tasks

1. **Grep for `ffmpeg` / `rawvideo` / `cv2` / `VideoWriter` / `moviepy` / `pygame.image.save` / `subprocess.Popen`:** done repo-wide (§1). `cv2`/`VideoWriter`/`moviepy` = zero first-party hits. `ffmpeg`+`rawvideo`+`Popen` converge on exactly the §2 scripts. Full `pygame.image.save` list in §4.
2. **Every script capable of generating, slicing, or exporting video:** `render_ko_video.py` (§2.1), `tools/render_trailer.py` (§2.2), `tools/render_trailer_v2.py` (§2.3). Plus the non-executable but operative `docs/PLAN_3_AUDIO.md` ffmpeg recipe (§2.4). Nothing else qualifies.
3. **Input per script:** `render_ko_video.py` = live game loop only (silent out). `tools/render_trailer.py` = live game loop + synthetic cards + pre-existing `menu_theme.mp3`. `tools/render_trailer_v2.py` = live game loop + synthetic finish + pre-existing audio (single MP3 or 3-stem WAVs) + ffprobe-measured silent MP4. `PLAN_3_AUDIO` recipe = pre-existing silent MP4 + pre-existing WAV stems. `trailer_bot.py` = live game loop in, key/aim actions out (feeder, not recorder).
