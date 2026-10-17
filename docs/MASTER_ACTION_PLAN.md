# MASTER ACTION PLAN — Video Capture Pipeline

**Synthesized from:** `docs/AUDIT_T1` … `docs/AUDIT_T8` (8 parallel read-only audits, 2026-09-26)
**Scope:** identify what is actually recording the video, prove whether it is live or replay,
locate the on-screen text defects, enumerate real combat checkpoints, and pick a remediation path.
**No source files were modified by this synthesis.**

---

## TL;DR

| Question | Answer |
|---|---|
| What is recording? | `tools/render_trailer_v2.py` with `ACARISTAN_EDITOR_CUT=1` → the 58 s `EDITOR_EDL` cut |
| Live or replay? | **Live.** Headless real `game_update`/`game_draw` ticks piped to ffmpeg. Zero replay files exist |
| The orange box? | `tools/render_trailer_v2.py:228-241` (`bug_tag()`), spine at `:240`, called at `:306,352,369,388` |
| 3 combat checkpoints? | `start_mission` / `start_mission2_after_sniper` / `start_mission3_kill_order_checkpoint` |
| Fix? | **Run the clean standalone `record_fresh_action.py`.** Do not surgically patch. Apply one separate 1-line `bug_tag` no-op only if the 58 s trailer is re-rendered |

---

## 1. The capture pipeline (T1 + T2 + T5 + T6)

### 1.1 There is no single recorder — there are three

| Script | Role | Output | Video-capable? |
|---|---|---|---|
| `tools/render_trailer.py` | Primary pipeline: pipe + boot + bot + mux | `trailers/trailer_60s.mp4`, `_silent.mp4`, `trailer_smoke.mp4`, `_vertical.mp4` | yes — generates, slices, exports |
| `tools/render_trailer_v2.py` | Finish wrapper; **no pipe of its own**, rebinds `rt.*` (`:530-539`) | same filenames | yes — generates via `rt.open_pipe`, exports |
| `render_ko_video.py` | Standalone 3-scene combat preview | `ko_phase5_preview.mp4` (repo root) | yes — generates |

`src/tools/trailer_bot.py` is **not** a recorder — zero `Popen`/`ffmpeg`/`tobytes`; it is a
deterministic operator *feeder* consumed by `src/app.py:2168-2179`. Frequently mis-classified; T1
explicitly fences it off. `tools/dev_panel.py:604` is a `Popen` false positive (launches game
instances). ~16 `pygame.image.save` scripts are stills-only.

No `cv2` / `VideoWriter` / `moviepy` / `av` / `pygame.movie` anywhere. `imageio_ffmpeg` is imported
unconditionally at `render_ko_video.py:23` but is **not in `pyproject.toml` and is not installed** —
that script cannot run today.

### 1.2 Which script actually produced the video on disk

T5 §6 settles it by timestamp + duration arithmetic:

| File | mtime | Duration |
|---|---|---|
| `tools/render_trailer_v2.py` | 2026-09-26 **23:10:37** | — |
| `trailers/trailer_60s_silent.mp4` | 2026-09-26 23:20:34 | **58.000 s** |
| `trailers/trailer_60s.mp4` | 2026-09-26 23:21:13 | **58.000 s** |
| `trailers/trailer_smoke.mp4` | 2026-09-26 23:00:51 | 10.000 s |

58.000 s matches `EDITOR_RUNTIME = 58.0` (`render_trailer_v2.py:45`) exactly and is asserted at
runtime by `:622-623`. Both files post-date the source's last edit by ~10 minutes.

> **The video was recorded by `tools/render_trailer_v2.py` running the 28-row `EDITOR_EDL` cut
> (`ACARISTAN_EDITOR_CUT=1`), not by `render_trailer.py`.**

### 1.3 Live rendering, conclusively (T2)

**Rendering live game ticks from scratch. Not replay, not saved frames.**

1. No `.rec` / `.demo` / `.pkl` / `.npz` / `.sav` / `.avi` / `.mov` anywhere; no `recordings/`,
   `captures/`, `replays/`, `renders/` directories. The only 4 MP4s are documented outputs.
2. Every `.mp4` reference in code is a **write target**. Zero hits for `VideoCapture`,
   `imageio.get_reader`, `av.open`, `moviepy`, `pickle.load`, `np.load` in `src/` or `tools/`.
3. Pipe direction is provably one-way:
   `game_update` → `game_draw` → `pygame.image.tobytes/tostring` → ffmpeg `rawvideo` stdin → MP4.
4. 60 sim ticks/s in, 30 frames/s out (`if frame % 2 == 0: feed(screen)`).
5. Dead time is **discarded pre-feed**, not sliced from a file: `preroll_until_contact()`
   (`render_ko_video.py:265-272`) and the 60-tick pre-roll (`render_trailer.py:665-672`).
6. `save_data.json` is campaign progress, and the renderers **sandbox it to a temp dir**
   (`render_trailer.py:37-40`) so they cannot consume real player state.
7. "Pre-recorded" string hits are in-fiction (Balaceanu's looping address, `m3/meta.py:302-331`),
   not technical.

Title cards, boot typewriter, broadcast banner, end cards are procedurally drawn `pygame.Surface`
frames fed through the same pipe — not composited from clips.

---

## 2. On-screen text defects (T5)

### 2.1 The orange box — exact origin

**`tools/render_trailer_v2.py:228-241` — `bug_tag()`.**

```python
def bug_tag(cap_text):
    act, _ = _split_cap(cap_text)              # tail DISCARDED
    ...
    t = FONT_BUG.render(act, True, (255, 150, 60))          # orange text
    by = 8                                                 # TOP of screen
    config.screen.blit(bg, (bx, by))
    pygame.draw.rect(config.screen, (255, 120, 0), (bx, by, 3, bh))   # ← line 240, ORANGE SPINE
    config.screen.blit(t, (bx + pad_x + 8, by + pad_y))
```

* **It is at the TOP** (`by = 8`), not the bottom. The original *bottom* box was
  `render_trailer.py:127-134 caption()` — already deleted per `docs/PLAN_4_VISUALS.md:9-12`.
* Called unconditionally at **4 sites**: `:306` (`_run_melee_rush`), `:352` (`run_gameplay`),
  `:369` (`run_menu`), `:388` (`run_walk`). Live sites: 306, 352.
* It is a raw `pygame` blit onto `config.screen` **outside the engine draw stack**, pasted after
  `rt.gc.game_draw(...)`. No engine flag, setting, or `show_*` toggle can suppress it.
* It is a **PLAN_4 §1.1 regression** — the identical widget PLAN_4 ordered deleted, re-anchored to
  the top in a file written after PLAN_4 landed.

### 2.2 The bizarre strings — already dead

| String | Live location | Rendered? |
|---|---|---|
| `glint to muzzle flash` | `render_trailer_v2.py:58` | no |
| `truck inspection` | `render_trailer_v2.py:63` | no |
| `laser to helmet-off` | `render_trailer_v2.py:65` | no |
| `hand on valve` | `render_trailer_v2.py:68` | no |
| `warehouse push` | `render_trailer_v2.py:177` (docstring only) | no |

All live strings sit in `EDITOR_EDL` (`:48-93`) as the 5th tuple element (`cap_text`), format
`HEAD // tail`. Two consumers: `_split_cap()` (`:176-181`) splits on the first `//`; `bug_tag()`
binds the tail to `_` and never renders it. `caption()` (`:220-225`) is a bare `return` and has zero
call sites. So the tails are **structurally unreachable pixels** in the current tree — the user's
video is a build older than 2026-09-26 23:10:37, since overwritten.

**Only the `HEAD` slug survives on screen** (`KILL-BOX`, `TANKER`, `CHECKPOINT`, `ARCHIVES`, …)
inside the orange box.

### 2.3 Collateral defects in the same class (T5 §7)

1. **The default (non-editor) render path is silently broken.** v2 rebinds `rt.run_gameplay` /
   `rt.run_walk` to 3-/4-parameter versions (`:315`, `:376`) but `render_trailer.py`'s own
   `main()` calls the 2-parameter forms (`:661`, `:673`). With `ACARISTAN_EDITOR_CUT` unset, every
   section raises `TypeError: missing required positional argument 'router'`, the broad `except`
   at `render_trailer.py:675-678` swallows it, and the render "succeeds" with **zero gameplay** —
   still printing `saved ...`.
2. **Engine HUD is fully on in every take**: `HOSTILES: 0`, `OBJECTIVE: … [E] (0/4)`, `VASILE:`
   subtitle bar, `BROKEN RADIO [E]` prompts, minimap, weapon/HP panels. PLAN_4 §1.3 explicitly
   rejects takes containing `[E]` / `(0/3)` / `WASD` objective panels.
3. `rt.mux_108p_trailer_mix` is installed but never called — the shipped trailer carries only the
   single `menu_theme.mp3` bed, not the 3-stem PLAN_3 mix.

---

## 3. The repetitive-scene problem (T6)

Two structurally identical defects, one in the game and one in the trailer.

**Game:** `route12_aftermath` is queued **3×** in `mission2_ending_shots`
(`m2/meta.py:98,116,121`) with three different speaker labels. `draw_route12_aftermath`
(`cutscenes/route12.py:1520-1529`) is a 9-line wrapper over `_draw_route12_checkpoint_base`
(`:960-1023`), which takes exactly one meaningful parameter (`tanker: bool`) and draws the truck at
hardcoded pixels. Per-shot `t` resets to 0 on every advance (`app.py:1958-1959`). The three rows
are **frame-for-frame replays**; `lighting` is a near no-op because `draw_sky_gradient` overwrites
the fill immediately after.

**Trailer:** `EDITOR_EDL` queues 7 Route 12 rows (`m2` ×5, `m2sniper` ×2) whose **labels are the
only differentiator**. `start_mission2` resets the mission every row, so the player always spawns
at (8,74); a 2.0–2.8 s take at 5 px/tick covers 9–13 tiles while the goal legs are 6–10 tiles.
**Every `m2` take is the same jog up the empty west approach road.** S09 "truck inspection",
S12 "hand on valve", S13 "tanker run", S14 "contact", S16 "blast" are one shot with five labels.
`render_ko_video.py:283` already fixed this for itself ("Combat-only timeline, **zero repeats**") —
the fix was never applied to `EDITOR_EDL`.

**There is no single timeline system** — five independent ones with three advance models
(input-gated `min_ms` with no `max_ms`; hardcoded frame counts; auto-advance frame counter;
objective completion; explicit seconds per EDL row) and three different duration units (frames /
milliseconds / seconds) for one concept.

---

## 4. Bot behaviour — why takes look the same (T4)

Two families, same trick, **zero perception, zero learning**:

* **Family A** `src/tools/trailer_bot.py` — hardcoded `(move_x, move_y, aim_x, aim_y, action)`
  waypoint lists, injected as `_FakeKeys` (deadzone ±8 px, full-speed-or-stopped), hooked in
  `app.py:2168-2179`. Only randomness is ±4 px aim jitter. The docstring says it outright:
  *"the bot does NOT pathfind."*
* **Family B** headless `Router` classes in `render_trailer.py:340-425`,
  `render_trailer_v2.py`, `render_ko_video.py:87-153`, `ko_playability_audit.py:64-160` — a fixed
  goal-tile list, A* interpolated between goals, `<24 px` advance, `stuck>40` → 30-frame jitter.

Same spawn + same goal list + same tick rate = **bit-identical path every run**. `m2: [(14,72),
(22,68),(30,62),(24,58)]` are sparse transit tiles, hence the long holds on empty asphalt.

**The aim bug both families share:** M2/M3 recompute `STATE.player.angle` from the OS mouse every
tick (`m2/update.py:335-338`, `m3/flow.py:642-648`). Under `SDL_VIDEODRIVER=dummy` the mouse never
moves, so the bots must write `angle` every frame — and they write it *before* `game_update`, so it
is overwritten before render. The captured sprite visibly aims at a stale direction while the
bullet leaves correctly.

---

## 5. Combat density & the 3 real checkpoints (T3 + T7 + T8)

### 5.1 One enemy class, one alert model

`Enemy` (`entities/enemy_ai.py:117`) is shared by all three missions. The alert model is
`alerted: bool` + `state ∈ {IDLE, PATROL, SEARCH, CHASE, ATTACK}` — there is no `ALERT` or `COMBAT`
state. The canonical "already fighting" 4-line recipe is duplicated in 6 places, and
`last_seen_pos` is **mandatory** (CHASE with `last_seen_pos=None` falls straight to SEARCH).

**Enemies cannot fire without LOS** (`_shoot` gated on `can_see`, `:470`) — place spawns on the
player's sight line, not merely nearby.

Per-mission override behaviour (critical for any staging attempt):
* **M1 respects the state you hand it** — and pre-alerting detonates the whole alarm beat on
  frame 1 (`m1/update.py:100-105` → `trigger_alarm_early`).
* **M2 force-alerts every enemy every frame** (`m2/update.py:646-658`) — appending an `Enemy` is
  sufficient; M2 has no stealth.
* **M3 re-derives `state` from its own target director after `Enemy.update`**
  (`m3/systems.py:1765-1799`) — only `alerted` + `last_seen_pos` matter.
* `alert_all()` is **not portable**: measured contact M1 1.2 s, M2 3.4 s, M3 **never** (guards
  revert to `PATROL` after the search timeout, `enemy_ai.py:417`).

### 5.2 The 3 checkpoints — combat live at t=0, right weapon in hand

| Act | Boot call | Enemies at t=0 | Weapon | CLI |
|---|---|---|---|---|
| **I — Black Notebook** | `gc.start_mission(preserve_timer=True)` | **9** — 7 `E` tiles + commander (hp 250) + miniboss (hp 400) | pistol 12+3, 2 molotovs | `--dev-m1` / `--jump m1` |
| **II — Quiet on Route 12** | `gc.start_mission2_after_sniper(preserve_timer=True)` | **4** — sniper marker (58,26) + 3 IPA grunts, all `alerted/CHASE` from the factory | **OS-12** 25 rd + 2 spares | `--dev-mission2-after-sniper` / `--jump m2-after-sniper` |
| **III — The Vostral** | `gc.start_mission3_kill_order_checkpoint(preserve_timer=True)` | **delayed ~2–4 s** — sweep director seeds wave 0 (shield 5,10 + guards 4,12 & 6,12), up to 9 concurrent + holdout stream | **K-9 SMG** 24 rd + 2 spares, Volkov ally | `--dev-mission3-kill-order` / `--jump m3-kill-order` |

**Verified fallback for Act III:** `gc.start_mission3_archives_checkpoint()` — 8 guards on build,
K-9, measured contact at 1.0 s.

**Rejected, with reasons:**
* `start_mission2()` — **worst offender in the codebase by an order of magnitude** (T7 §5):
  `_build_world` spawns **zero** enemies; the first team is ~3510 px (≈12 s) away. This is the
  root cause of the 5 identical `m2` trailer takes.
* `start_mission3_breakout_checkpoint()` — player is **disarmed with a chair leg** and the doorway
  is gated behind an 8-stroke whittle minigame the bot cannot perform. All three legacy scripts
  needed a `stage_breakout_flags()` monkeypatch for this.
* `start_mission3()` (interrogation), `--dev-safe`, `--dev-mission2-truck`, `--m3-ledger` — all
  explicitly zero out `STATE.enemies`.

### 5.3 Measured yield (T8, live prototype, 600 ticks = 10.00 s per act)

| Act | Contact | Shots | Kills | Wall |
|---|---|---|---|---|
| I | tick 48 (0.80 s) | 50 | 6 | 8.7 s |
| II | tick 37 (0.62 s) | 75 | 7 | 27.4 s |
| III | tick 226 (3.77 s) | 116 | 6 | 20.2 s |

`ffprobe`: `h264 / 1000x700 / yuv420p / 30 fps / nb_frames=300` per act — exactly 10.000 s each.

---

## 6. Remediation decision

### RECOMMENDED: run the clean standalone `record_fresh_action.py`

Rationale, in order of weight:

1. **The existing default path is already broken** (T5 §7.2). Patching means fixing a silent
   `TypeError`-swallowing failure mode *and* the `bug_tag` box *and* the HUD clutter *and* the
   duplicate-`m2` EDL — four unrelated problems across two entangled files with an in-file
   monkeypatch install block.
2. **`bug_tag` is a one-line fix, not a pipeline fix.** Suppressing it leaves the T5 §7.4 HUD
   violations (`OBJECTIVE: … [E] (0/4)`, `HOSTILES: 0`, `VASILE:` subtitles, minimap) — the same
   PLAN_4 §1.3 clause, and the actual thing viewers see.
3. **The aim bug lives in the bots, not the engine.** A surgical patch would have to replicate the
   mouse-driven aim in **four** places (`render_trailer.py`, `render_trailer_v2.py`,
   `render_ko_video.py`, `trailer_bot.py`) and re-verify each. That is a larger, riskier diff than
   writing one clean ~330-line file that fixes it once.
4. **Zero source edits required.** The standalone does not import `app`, so the level editor,
   dev console, crosshair, menu cursor, and FSM fade are *structurally* absent rather than
   flag-gated. No `src/` change, no `smoke_test.py` risk.
5. **Proven.** T8 validated the full architecture end-to-end before this document was written:
  3 clean MP4s, exact 10.00 s, verified frame counts, combat contact in every act.
6. **Also kills the remaining legacy bugs:** CWD-dependent `resource_path` (`chdir` fix), real
   `save_data.json` writes (`m1/main.py:52`), the missing `imageio_ffmpeg` dependency, frame-rate
   coupling, and the swallowed-section-failure silent no-op.

### Scope boundary — the standalone is not a trailer editor

`record_fresh_action.py` produces **clean combat footage**, not the 58 s edited cut with title
cards, act cards, and the audio bed. Those remain `render_trailer_v2` + `PLAN_3_AUDIO` territory.

### Recommended sequencing

| # | Action | Rationale |
|---|---|---|
| 1 | Build + run `tools/record_fresh_action.py` | primary deliverable: clean 3-act combat capture |
| 2 | *(optional, 1 line)* `return` as first statement of `bug_tag()` (`render_trailer_v2.py:228`) | hygiene, **only if** the 58 s trailer is re-rendered; T5 Option A |
| 3 | *(deferred)* Fix the `rt.run_gameplay` signature mismatch | only needed if the non-editor path is used again |
| 4 | *(deferred)* Give `EDITOR_EDL` genuinely distinct `key`s, or drop labels | T6 §8.3 — 5 identical `m2` takes |
| 5 | *(deferred, game-side)* Collapse the 3× `route12_aftermath` queue + add a `variant` param | T6 defect #1/#2 — separate from capture |

### Explicitly NOT recommended

* **Editing the `EDITOR_EDL` string literals** (T5 §4.4 Option C). Cosmetic only; the orange box
  and the `HEAD` slug still render. Looks like a fix while the defect persists.
* **Engine-level spawn hooks / `force_fight()` injection** (T7 §6). Requires editing `src/`,
  contradicts the read-only mandate, and T8 proved the seek-and-fight driver reaches contact in
  every checkpoint without it.
* **Rebuilding the `route12` renderer now.** Real bug, but it is a *game* defect in
  `src/cutscenes/route12.py`, not a capture defect. File it separately.

---

## 7. Cross-audit defect index

| Sev | Defect | Location | Audit |
|---|---|---|---|
| High | `route12_aftermath` queued 3× → frame-identical replays | `m2/meta.py:98,116,121` + `cutscenes/route12.py:1520-1529` | T6 |
| High | `_draw_route12_checkpoint_base` has no variant param — truck is always the same empty slab | `cutscenes/route12.py:960-1023` | T6 |
| High | 5 identical `m2` EDL takes; labels describe unreachable content | `render_trailer_v2.py:62-75` | T6 |
| High | `bug_tag()` PLAN_4 §1.1 regression, outside the engine draw stack | `render_trailer_v2.py:228-241` (spine `:240`) | T5 |
| High | Default render path silently produces zero gameplay (`TypeError` swallowed) | `render_trailer_v2.py:315,376` vs `render_trailer.py:661,673,675-678` | T5 |
| High | `imageio_ffmpeg` imported but undeclared/uninstalled → `render_ko_video.py` cannot run | `render_ko_video.py:23` vs `pyproject.toml` | T1, T8 |
| Med | Engine HUD fully on in every take (`[E]`, `(0/4)`, subtitles, minimap) | PLAN_4 §1.3 violation | T5 |
| Med | No `max_ms` on cutscene shots — soft-lock possible | `app.py:1867-1894` | T6 |
| Med | `_beat_now` uses `pt == f`; a skipped/duplicated tick drops the beat forever | `m2/meta.py:693-695` + `sniper.py:988-1104` | T6 |
| Med | `route12_tanker` dispatcher branch unreachable | `cutscenes/engine.py:274-275` | T6 |
| Med | Bots write `player.angle` pre-update; M2/M3 overwrite from a dead mouse every tick | `m2/update.py:335-338`, `m3/flow.py:642-648` | T4, T8 |
| Med | `alert_all()` non-portable — M3 guards de-alert after search timeout | `enemy_ai.py:417` | T8 |
| Med | `m1/update.py:100-105` — pre-alerting M1 detonates the full alarm on frame 1 | `m1/update.py` | T7 |
| Med | `resource_path()` is CWD-relative; no legacy script chdirs | `core/config.py:7-12` | T8 |
| Med | Capture runs write the player's real `save_data.json` | `m1/main.py:52` → `save_system.py:81` | T8 |
| Low | `silence_start` / `silence_frames` / `muzzle_flash` defined, never dispatched | `m2/meta.py:654-687` | T6 |
| Low | Two disagreeing hardcoded rain-scene sets | `app.py:1942-1949` vs `1964-1965` | T6 |
| Low | Three duration units (frames / ms / seconds) for one concept | `m2/draw.py:3921` vs `meta.py:73` vs `render_trailer_v2.py:53` | T6 |
| Low | `lighting` key overwritten by `draw_sky_gradient`; survives only in letterbox bars | `cutscenes/engine.py:22` → `config.py:145` | T6 |
| Low | `is_transition` set on one row, read nowhere | `m2/meta.py:150` | T6 |
| Low | Stale comment: says 3s/6s, constants are 7s/12s | `m3/interrog.py:308`, `flow.py:127-128` | T6 |
| Low | `mux_1080p_trailer_mix` installed but never called — no 3-stem mix shipped | `render_trailer_v2.py:539` vs `editor_main` | T5 |
| Low | Dev-console `spawn_enemy` spawns un-alerted, 0 flags — useless for density | `core/console.py:56` | T7 |
