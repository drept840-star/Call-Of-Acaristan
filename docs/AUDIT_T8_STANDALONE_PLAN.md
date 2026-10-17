# T8 — Standalone Capture Architect: `record_fresh_action.py`

**Status:** READ-ONLY investigation. No source file was modified.
**Deliverable:** this blueprint + a validated prototype (numbers below are measured, not estimated).
**Target artifact:** one new file, `tools/record_fresh_action.py`, self-contained, zero engine edits.

---

## 1. What the engine actually gives us (verified)

`src/app.py` is a **module-level, non-reentrant** main loop (`src/app.py:2735-2866`) that calls
`pygame.display.flip()` every frame. It cannot be driven headlessly. Legacy capture scripts therefore
bypass `app.py` entirely and drive the *mission* layer directly:

```
gc.start_mission*()          # boot a checkpoint, populates STATE
gc.game_update(keys)         # returns (cam_x, cam_y) or None
gc.game_draw(cam_x, cam_y)   # paints into config.screen
```

Verified headless facts (measured on this machine, `SDL_VIDEODRIVER=dummy`):

| Fact | Value | Source |
|---|---|---|
| `config.screen` **is** the display surface at 1000x700 under the dummy driver | `True` | `src/core/config.py:31` |
| `pygame.mouse.set_pos()` works under the dummy driver and `get_scaled_mouse()` returns it verbatim | `(321,222) -> (321,222)` | `src/core/config.py:15-30` |
| `pygame.display.set_mode(..., SCALED)` is legal headless | prints `Warning: no fast renderer available` only | — |
| `imageio_ffmpeg` is **not installed** | `ModuleNotFoundError` | `render_ko_video.py:23` will crash today |
| `ffmpeg` is on PATH | `C:\ffmpeg\bin\ffmpeg.exe` | — |
| `python` | 3.14.3, `pygame-ce 2.5.7`, `numpy 2.5.1` | `.venv` |

Per-checkpoint cost (600 sim ticks = 10.0 s of video, one process, sequential):

| Act | Boot | Enemies at boot | First `game_draw` | Steady frame |
|---|---|---|---|---|
| M1 warehouse | 4 ms | 9 | 36 ms | 9.6 ms |
| M2 kill-box | 35 ms | 4 (OS-12) | 307 ms | 18.6 ms |
| M3 Kill Order | 12 ms | 0 (sweep director seeds at ~t=4 s) | 23 ms | 23.7 ms |
| M3 Archives (alt) | 34 ms | 8 (K-9) | 31 ms | 15.4 ms |

---

## 2. The six legacy bugs this design kills

### B1 — Mouse-derived aim is overwritten every frame  *(the big one)*
All three missions recompute the player's facing from the mouse **inside `game_update`**:
`src/missions/m1/update.py:496-501`, `src/missions/m2/update.py:335-338`,
`src/missions/m3/flow.py:642-647`.

Every legacy bot (`tools/render_trailer.py:313`, `render_ko_video.py:182`,
`src/tools/trailer_bot.py:146`) sets `STATE.player.angle` **before** calling `game_update`, then
fires **after**. Net effect: the bullet leaves along the correct vector, but the *rendered sprite
rotation* is re-derived from a dead mouse at (0,0) — so in every captured frame the operator is
visibly aiming at the top-left corner while shooting an enemy to the right.

**Fix:** drive the real input. `aim_world(wx, wy)` sets
`pygame.mouse.set_pos((wx - camera_x, wy - camera_y))` *before* `game_update`, and the engine's own
aim math does the rest. Verified: target 300 px to the right ⇒ `player.angle == 0.0`.

### B2 — CWD-dependent asset resolution
`core.config.resource_path()` falls back to `os.path.abspath(".")` (`src/core/config.py:7-12`).
No legacy script calls `os.chdir`, so launching from anywhere but the repo root silently loses all
fonts, `bg.jpg`, and `assets/art/*` (procedural fallbacks everywhere). **Fix:** `os.chdir(ROOT)` as
line 1 of the script.

### B3 — Real save file is written by a capture run
`missions.m1.main.start_mission` calls `save_system.set_slot_progress("m1")`
(`src/missions/m1/main.py:52`) → `json_store.atomic_write(SAVE_FILE, …)`
(`src/core/save_system.py:81`). A capture therefore mutates the player's campaign save.
**Fix:** repoint `save_system.SAVE_FILE` **and** `settings_store.SAVE_FILE` into a `tempfile`
scratch dir *before* any mission boot (3 lines; `render_trailer.py:36-40` got this right, the other
scripts did not).

### B4 — `imageio_ffmpeg` hard dependency
`render_ko_video.py:23` imports it unconditionally; it is not in `pyproject.toml` and is not
installed. **Fix:** resolve ffmpeg in order `$FFMPEG` → `shutil.which("ffmpeg")` →
`C:\ffmpeg\bin\ffmpeg.exe`, and only then try `imageio_ffmpeg` as a last resort.

### B5 — HUD/overlay suppression is incomplete and inconsistent
Patching `ui.hud.draw_objective_panel` does **nothing**: every mission part module did
`from ui.hud import draw_objective_panel` at import time, binding the *original* function into its
own globals. Worse, the three missions call it from **three different modules**:
`missions.m1.draw:1471`, `missions.m2.draw:5279`, `missions.m3.systems:909` — legacy patches that
only touch `missions.m*.draw` silently leave Act 3's objective banner and PA caption on screen
(reproduced: see §6).

**Fix:** a `sys.modules` sweep that rebinds the attribute on **every** module that holds a
reference to the original function object. Order-independent, no module list to maintain.

### B6 — Frame-rate/duration coupling
`render_trailer_v2` feeds only every 2nd tick but restarts `FRAME[0] = 0` per section, and wraps
takes in `try/except` that "keeps the tape rolling" — a crashing act silently ships a 0-second
segment. **Fix:** one ffmpeg process per act, exact frame accounting, hard failure + non-zero exit.

---

## 3. Architecture

```
tools/record_fresh_action.py          (single file, ~330 lines, no new packages)
│
├─ 0. PRE-FLIGHT            chdir, SDL env, sys.path, ffmpeg resolve, save/settings redirect
├─ 1. BOOT                  boot one checkpoint -> populated STATE, camera already snapped
├─ 2. STRIP                 kill debug/UI clutter (HudPolicy, §4)
├─ 3. DRIVE                 600 sim ticks @ 60 Hz; mouse-aim + A* seek + strafe + fire
├─ 4. FEED                  every 2nd tick -> raw RGB bytes -> ffmpeg stdin (30 fps)
├─ 5. VERIFY                per-act assertions + report.json; non-zero exit on failure
└─ 6. REPORT                stdout table + trailers/fresh_action/report.json
```

Explicitly **not** imported: `app`, `ui` (menu/FSM), `core.fsm`, `core.level_editor`,
`core.console`, `core.ambience`, `src/tools/*`. Not importing `app` is what guarantees
zero debug overlays: the level editor, dev console, crosshair, menu cursor, and FSM fade
overlay are all drawn from `app.py`'s loop, so they are structurally absent rather than
switched off.

### Module budget (the "unbloated" contract)

| Unit | Lines | Job |
|---|---|---|
| preflight | 30 | env, paths, ffmpeg, scratch save |
| `Ticker` | 25 | ffmpeg rawvideo pipe |
| `apply_hud_policy` | 30 | clutter suppression (§4) |
| `Router` | 30 | walkability grid + `_astar` |
| `Driver` | 110 | perception, aim, movement, fire, sim step |
| `ACTS` table | 30 | the 3 checkpoints |
| `capture_act` / `main` | 60 | loop, verify, report |

### Why `pygame.mouse.set_pos` instead of monkeypatching
It is a real input event, so it exercises the engine's own aim path (recoil kick, spread,
weapon-raise gates, M3's `weapon_raised` checks). It needs no patching, works under the dummy
driver, and is 2 lines.

---

## 4. Clutter suppression — `HudPolicy`

Three levels. Taxonomy matters: the engine has **no** debug labels or FPS overlay (verified by
grep across `src/`), so "debug labels" in practice means *scaffolding the legacy scripts drew
themselves* (act bug tag, storyboard pill, `SMOKE CHECK` prism) — which a standalone script simply
never draws. What remains is real UI, and it splits cleanly.

### `--hud clean` (DEFAULT) — removes every overlay, keeps gameplay panels

| Target | Mechanism | Verified |
|---|---|---|
| Objective banner (all 3 acts) | rebind `draw_objective_panel` on every holder module | gone in all 3 frames |
| Pinned radio / PA captions | rebind `draw_pinned_radio` on every holder module | gone |
| Minimap | `STATE.show_minimap = False`, **re-applied after every boot** (`start_mission*` sets it back to `True` — `m1/main.py:72`, `m2/starts.py:55`) | gone |
| Startup hint text (`"[G] or RIGHT-CLICK to throw a molotov"`, `m1/main.py:136`) | `STATE.floating_texts.clear()` after boot | gone |
| M3 objective nav arrow + label | rebind `missions.m3.draw._draw_objective_waypoint` | gone |
| Radio queue so nothing types in later | `interactions.clear_radio_queue()`; never call `pump_radio()` | gone |

The rebind sweep (order-independent, ~6 lines):

```python
def _rebind_everywhere(name, replacer):
    orig = getattr(ui.hud, name)
    for mod in list(sys.modules.values()):
        if getattr(mod, name, None) is orig:
            setattr(mod, name, replacer)
```

Kept on purpose: HP/ammo/molotov panels, `HOSTILES: n` chip, in-world `[E]` prompts, prop labels,
enemy radio bubbles, M3's in-world `draw_combat_reticle`. These are diegetic — the game's own look.

### `--hud bare` — also removes the bottom-left HUD cluster
The ammo/HP/molotov cluster is **inline** in M1 (`missions.m1/draw.py:1441-1615`, inside
`_game_draw_inner`; there is no `_draw_hud` function to patch) but is a single function in
M2 (`missions/m2/draw.py:5247 _draw_hud`) and M3
(`missions/m3/systems.py:907 _draw_mission3_hud`).

Two implementations, both measured on a real Act-1 frame:

| Strategy | Result |
|---|---|
| **A — flat plate** `Surface(SRCALPHA).fill((4,5,7,242))` over `(18,506,258,172)` | **Rejected.** Bright green HUD text still ghosts through at 5 % alpha, and the HOSTILES chip is a separate rect. Reads as a bug. |
| **B — adjacent-strip mirror** `screen.blit(screen, (18,506), Rect(292,506,258,172))` | **Accepted.** Bottom-left cluster fully gone, replaced by plausible floor; seam invisible in the dark corridor art. Verified on a live frame. |

`bare` therefore uses **B for all three acts** (one uniform code path, no per-mission branching) and
patches `_draw_hud` / `_draw_mission3_hud` to no-ops as a belt-and-braces second layer.

Known artifact, documented honestly: a world-space floating text inside the *source* strip ghosts
into the corner. Mitigation (4 lines, default on): drop `STATE.floating_texts` entries whose
screen-projected box intersects the source rect.

Documented rects (override with `--hud-rects`):

| Cluster | Rect | Source rect (mirror) |
|---|---|---|
| M1 bottom-left (molotov+ammo+HP) | `(18, 506, 258, 172)` | `(276, 506, 258, 172)` |
| M1/M2/M3 HOSTILES chip | `(18, 18, 150, 30)` | `(168, 18, 150, 30)` |

### `--hud full`
Zero patching. Escape hatch for A/B comparison.

---

## 5. The three checkpoints

Chosen for *"combat is LIVE at t=0 with the right weapon in hand"* — i.e. no cutscene to skip, no
objectives to click, no staging flags to fake.

| Act | Boot call | Weapon | Combat at t=0 | Nav grid solids |
|---|---|---|---|---|
| **I — Black Notebook** | `gc.start_mission(preserve_timer=True)` | pistol 9 mm | 9 hostiles (3 patrol rows + commander 250 hp + miniboss 400 hp) | `("C","W")` on `missions.m1.map.mission1_map` |
| **II — Quiet on Route 12** | `gc.start_mission2_after_sniper(preserve_timer=True)` | OS-12 (25 rd) | 4-body IPA squad incl. sniper, player pre-placed at `KILLBOX_COVER_POSITIONS[0]` | `("C","B","T")` on `missions.m2.world.MISSION2_MAP` |
| **III — The Vostral** | `gc.start_mission3_kill_order_checkpoint(preserve_timer=True)` | K-9 SMG (24 rd) | sweep director seeds wave 0 (shield + 2 guards) at ~t=4 s; Volkov ally active | `("C","g","B")` on `missions.m3.maps.MISSION3_KILL_ORDER_MAP` |

Why these and not the obvious ones:

* **`start_mission2_after_sniper`, not `start_mission2`** — the latter lands in
  `STAGE_INVESTIGATE` with zero hostiles; you would have to walk the whole evidence phase first.
* **`start_mission3_kill_order_checkpoint`, not `…_breakout_checkpoint`** — breakout spawns the
  player *disarmed with a chair leg* and gates the doorway behind an 8-stroke whittle minigame the
  bot cannot perform. Legacy scripts all needed a `stage_breakout_flags()` monkeypatch for this
  (`render_ko_video.py:250`, `render_trailer_v2.py:157`). Kill Order needs no staging.
* `start_mission3_archives_checkpoint` is a verified **fallback** for Act III (8 guards, K-9,
  contact at 1.0 s) if the KO sweep proves too slow on a given machine.

**Do not** use `alert_all()` (force every enemy to `CHASE`). Measured: it works for M1 (contact
1.2 s) and M2 (3.4 s) but is **useless for M3** — `enemy_ai.py:417` clears `alerted` and reverts to
`PATROL`/`IDLE` after the search timeout, so all 8 Archives guards gave up inside 5 s. Seek-and-fight
works everywhere; alert-all is not portable.

---

## 6. `Driver` — the combat loop

One tick, in this exact order:

```
1  perceive   nearest living enemy (radius 2400)                    -> target
2  perceive   LOS to target via weapons._wall_blocks_line(...)      -> seen?
3  aim        if seen:  lead the target by dist/30 and set the MOUSE
              else:     set the MOUSE at the target (keeps the gun tracking while walking)
4  move       seen:      close if d>330, back off if d<170, else strafe (25-tick A/D toggle)
              not seen:  A* to the target's tile, repath every 30 ticks, follow the path
5  harness    p.hp = p.max_hp ; top up the ACTIVE weapon's magazine only
6  simulate   cam = gc.game_update(keys)
7  fire       weapons.handle_shoot()      # after update; weapon cooldown self-gates the rate
8  render     gc.game_draw(cam)
9  pump       pygame.event.pump()
```

Why this shape:

* **Aim before update, fire after.** The engine owns aim (B1); `handle_shoot` is the only correct
  entry point, and it is already gated by `shot_cooldown` (pistol 12 f / OS-12 8 f / K-9 5 f) and by
  `weapon_raised` / `weapon_swap_timer` — so calling it every tick yields the true per-weapon rate
  with no extra logic. Legacy `combat_post` gated on `(FRAME[0]//2)%10 < 6`, which is both
  frame-counter coupled and slower than the real weapon.
* **Lead = `dist / 30`**, not `dist / 24`. Enemy bullets run 18-24 px/frame; 30 errs long against
  fast movers and measurably raised hit rate versus the legacy constant.
* **A\* only for approach.** `entities.enemy_ai._astar` on a grid built from the mission char map
  plus locked-door `collision_rect`s. Reused as-is — no reimplementation, and it is already the
  engine's own pathfinder. Greedy "walk at the nearest enemy" deadlocks on walls; this does not.
* **Top up only the active weapon.** `STATE.ammo_in_mag` vs `os12_ammo_in_mag` vs `k9_ammo_in_mag`
  — the legacy `top_up()` only handled K-9 + the M1 fields, so M2 OS-12 takes ran dry and stalled.

### Validated combat yield (600 ticks, 300 fed frames, single process)

| Act | Contact | Shots fired | Kills | Enemies left | Wall clock |
|---|---|---|---|---|---|
| I | tick 48 (0.80 s) | 50 | 6 | 3 | 8.7 s |
| II | tick 37 (0.62 s) | 75 | 7 | 4 | 27.4 s |
| III | tick 226 (3.77 s) | 116 | 6 | 3 | 20.2 s |

Output verified with `ffprobe`: `h264 / 1000x700 / yuv420p / 30 fps / nb_frames=300` per act,
i.e. exactly 10.00 s. Whole run ≈ 57 s wall for 30 s of footage.

---

## 7. ffmpeg pipe

One process **per act**, opened after the act boots and closed before the next:

```
ffmpeg -y -f rawvideo -pix_fmt rgb24 -s 1000x700 -r 30 -i -
       -an -c:v libx264 -pix_fmt yuv420p -crf 16 -preset medium
       -movflags +faststart trailers/fresh_action/act<N>.mp4
```

* Feed `pygame.image.tobytes(config.screen, "RGB")` on **every 2nd sim tick** → 30 video frames per
  60 sim ticks. Video duration is a function of *frame count*, not wall clock, so a slow machine
  produces the same 10.000 s clip, just later. (`stdin.write` blocks on back-pressure; that is the
  intended throttle.)
* `stderr=DEVNULL`; on non-zero exit, surface the last 2 KB — legacy swallowed it entirely.
* Per-act files, not one long tape: a failure in Act II must not cost Act I and III.
  `--merge` concatenates via the concat demuxer (`-c copy`) into
  `trailers/fresh_action/combat_30s.mp4`.
* Audio: intentionally `-an`. A capture is a picture source; the music/SFX bed is muxed later in
  post (see `docs/PLAN_3_AUDIO.md`).

---

## 8. Isolation & determinism

| Concern | Handling |
|---|---|
| Save / settings writes | `save_system.SAVE_FILE` + `settings_store.SAVE_FILE` → `tempfile.mkdtemp()` (B3) |
| Audio | `SDL_AUDIODRIVER=dummy`; `audio.set_master_volume(0)`; pump `audio.update()` per tick; `audio.stop_all()` + `audio.stop_mission3_alarm()` between acts |
| RNG | `random.seed(20260926)` immediately before **each** boot, so a single act is reproducible in isolation |
| Real-time leakage | `pygame.time.get_ticks()` drives the radio director (`interactions.py:255`), M1 breach flicker, M2 heartbeat, enemy sweep offset (`enemy_ai.py:403`). Unpumpable and sim-fps dependent. Mitigated by never calling `pump_radio()` and by `clear_radio_queue()`; residual effect is a ≤1-frame visual wobble, not a structural nondeterminism. **Do not claim bit-exact reproducibility.** |
| Mission bleed | Each act re-boots from scratch; `STATE.reset()` runs inside `start_mission2/3`. Confirmed clean when running I→II→III in one process. Act tables capture the **concrete** map constants (`MISSION3_KILL_ORDER_MAP`, never the mutable `missions.m3.maps.MISSION3_MAP`). |
| Art / static bakes | Left ON (`ACA_ART` unset, `ACA_STATIC` unset) — matches shipping look. `ACA_STATIC=off` roughly doubles M2/M3 frame cost. |

---

## 9. CLI

```
python tools/record_fresh_action.py [options]

  --act {1,2,3,all}        which checkpoint(s)          (default: all)
  --seconds N              per-act clip length          (default: 10)
  --hud {clean,bare,full}  clutter policy               (default: clean)
  --out-dir PATH           output directory             (default: trailers/fresh_action)
  --merge                  also emit concat combat_30s.mp4
  --crosshair              overlay hud.draw_gameplay_crosshair (off by default)
  --seed N                 RNG seed                     (default: 20260926)
  --keep-going             warn+continue on act failure (default: fail fast, exit 1)
  --hud-rects "x,y,w,h;…"  override the bare-mode mask rects
  --list                   print the act table and exit
```

Exit codes: `0` all acts verified · `1` one or more acts failed · `2` preflight failure
(no ffmpeg, no player after boot).

---

## 10. Per-act verification (the "verified checkpoints" requirement)

`capture_act` asserts before closing the pipe:

1. `STATE.player is not None` after boot, else exit 2.
2. `frames_written == seconds * 30` exactly.
3. `contact_tick >= 0` and `contact_tick < 0.5 * total_ticks` — the clip is combat, not a walk.
   *(Act III measured 3.77 s of a 10 s budget; the 5 s ceiling gives headroom, the 0.5 s floor
   would fail Act III, so this threshold must be configurable — default 0.6 × ticks.)*
4. `kills >= 2` — the gun is actually connecting.
5. Non-blank: ≥ 12 distinct luma buckets across a 5-frame sample (catches a black or frozen pipe).
6. `ffprobe` the finished file: `nb_frames` matches, `pix_fmt == yuv420p`.

`report.json` per act: `act, frames, seconds, contact_tick, contact_sec, shots, kills,
enemies_left, mean_luma, wall_sec, bytes, out`. Plus a stdout table.

---

## 11. Implementation order

1. **Skeleton + preflight** — chdir, env, ffmpeg resolve, scratch save. `python tools/record_fresh_action.py --list` must print the act table with zero side effects.
2. **`Router`** — grid from char map + locked doors; unit-check with `--act 3` reaching contact.
3. **`Driver.tick`** — mouse aim + LOS + strafe. Verify `player.angle` matches the target bearing.
4. **`Ticker`** — ffmpeg pipe. Verify `ffprobe nb_frames == seconds*30`.
5. **`apply_hud_policy`** — start at `clean`; confirm all three frames by exporting PNGs.
6. **`bare`** — mirror-strip + `_draw_hud` / `_draw_mission3_hud` patches + rect table.
7. **Verification block + `report.json`**.
8. **`--merge`**.
9. Gate: `python tools/smoke_test.py` must still print `SMOKE TEST: OK`, and
   `python -m compileall -q src` must stay clean (the script lives in `tools/`, so `src` is
   untouched by construction — but run both to prove it).

## 12. Risks

| Risk | Mitigation |
|---|---|
| KO sweep is slow to seed on a weak machine | `--act 3` already falls back inside the driver; if contact exceeds the ceiling, the run reports the failure and suggests `--act-alt archives` (verified: contact 1.0 s, 8 guards) |
| M3 KO frame cost 23.7 ms/tick ⇒ ~25 fed fps on a slow box | Output fps is frame-count-driven, so the clip is still exactly 10.000 s. Raise `--seconds` or accept slower wall clock. |
| `bare` mirror ghosts a world floating text | Per-tick filter drops floating texts intersecting the source rect (default on, `--hud bare --no-ghost-filter` to disable) |
| Future mission code moves the objective/HUD call sites | The `sys.modules` sweep has no module list to maintain; the Act-I/II/III **act table** is the only place to update, and `--list` prints it |
| Engine adds a new overlay inside `app.py`-adjacent code | Structurally immune: `app` is never imported |

## 13. Explicitly out of scope

* No source edits (`src/` untouched).
* No new shared modules — one file, per the brief.
* No audio muxing (post-production concern, `docs/PLAN_3_AUDIO.md`).
* No 1080p upscale / vertical crop — a clean 1000x700 native master is the deliverable; scaling
  belongs in the same post pass as the audio bed.
