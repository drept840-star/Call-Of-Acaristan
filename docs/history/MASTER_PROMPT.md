# MASTER PROMPT — Call of Acaristan: The Big Polish & Fix Pass

> **Who this is for:** an autonomous coding agent working inside the `Call of Acaristan` repository (`First try/`).
> **What it is:** a single, self-contained brief covering **ten** issues, the order to attack them, the files that own each problem, what "done" means, and how to prove it.
> **Tone of the work:** this is a shipped-quality polish pass, not a hotfix sprint. Take the time. Read before you write. Prove every change.

---

## Table of contents

0. [Ground rules (read first, obey always)](#0-ground-rules-read-first-obey-always)
1. [Skills: how to use `SKILLS/`](#1-skills-how-to-use-skills)
2. [Orientation: what you must read before Task 1](#2-orientation-what-you-must-read-before-task-1)
3. [Execution order & workflow per task](#3-execution-order--workflow-per-task)
4. [Task 1 — The gigantic voice-line pass](#task-1--the-gigantic-voice-line-pass)
5. [Task 2 — M5 KRAP Depot cutscene rework](#task-2--m5-krap-depot-cutscene-rework)
6. [Task 3 — Unify the gameplay camera across all missions](#task-3--unify-the-gameplay-camera-across-all-missions)
7. [Task 4 — Weapon detached from Biribel in the new uniform](#task-4--weapon-detached-from-biribel-in-the-new-uniform)
8. [Task 5 — Biribel renders blue when the uniform is black](#task-5--biribel-renders-blue-when-the-uniform-is-black)
9. [Task 6 — Radio-line UI: full overhaul](#task-6--radio-line-ui-full-overhaul)
10. [Task 7 — Procedural art → real sprites (generator scripts)](#task-7--procedural-art--real-sprites-generator-scripts)
11. [Task 8 — Remove speaker headers from cutscenes](#task-8--remove-speaker-headers-from-cutscenes)
12. [Task 9 — Mission Failed screen always says BLACK NOTEBOOK](#task-9--mission-failed-screen-always-says-black-notebook)
13. [Task 10 — MAG Print Works door: the interior isn't there](#task-10--mag-print-works-door-the-interior-isnt-there)
14. [Cross-cutting QA checklist](#cross-cutting-qa-checklist)
15. [Deliverables & final report format](#deliverables--final-report-format)
16. [Things you must NOT do](#things-you-must-not-do)
17. [Appendix A — File map cheat-sheet](#appendix-a--file-map-cheat-sheet)
18. [Appendix B — Known facts discovered during scoping](#appendix-b--known-facts-discovered-during-scoping)

---

## 0. Ground rules (read first, obey always)

1. **`AGENTS.md` is law.** Read it in full before touching anything. In particular:
   - The shell is **Windows PowerShell**. No `head`, `grep`, `cat`. Use `Select-String`, `Get-Content`, `Select-Object -First N`, or `python -c "..."`.
   - Run everything from the repo root (`First try/`). Game code lives in `src/`; when scripting, `sys.path.insert(0, 'src')`.
   - Package `__init__.py` files for `missions.m1`, `missions.m2`, `missions.m3`, `ui`, `cutscenes` (and the same pattern in `m4`/`m5`) are **re-export facades**. Edit the part modules (`map.py`, `flow.py`, `systems.py`, `draw.py`, `widgets.py`, …). Never inline logic in a facade except the existing `_LIVE_STATE` / `__getattr__` block.
   - **Shared mutable state rule:** module globals that are rebound after import live in ONE owner module and are accessed elsewhere only via `import owner.path as _o; _o.name`. Never `from owner import mutable_name` (it snapshots and goes stale). Never rebind through a facade.
   - **Acyclic imports at load time.** Parts may top-level-import only earlier-loading parts (facade order = load order). Anything later goes in a function-level import marked `# lazy:`.
   - **Map contract:** runtime maps stay `list[str]`. Author through `src/core/mapbuilder.py`. `MapBuilder.validate()` must return `[]`. If you move a door row, update its consumer.
   - **engine3d:** create renderers with `engine3d.Renderer(...)` (GL with software fallback). Never switch the window to `pygame.OPENGL`. Characters go through `r.add_humanoid(...)`. Don't reach into `r._items`. Layers keep painter meaning.
2. **The gate after every task (no exceptions):**
   - `python tools/smoke_test.py` → must print `SMOKE TEST: OK`.
   - `python -m compileall -q src` → must be silent.
   - Any renderer / 3D cutscene change → `python tools/engine3d_check.py` (and `--shots` for visual parity).
   - Pygame noise like `Loaded optional sound ...` or `Warning: no fast renderer` is normal, not a failure.
3. **Evidence or it didn't happen.** Every visual change gets before/after screenshots saved under `shots/polish_pass/<task-number>/`. Every logic change gets either a smoke-test check, an audit script, or a reproducible repro note.
4. **Small, reviewable commits/changesets per task.** Don't mix tasks in one change. If you must touch a shared file for two tasks, do it in two passes.
5. **No silent scope creep.** If you notice an unrelated bug, log it in the final report under "Found, not fixed" instead of fixing it mid-task (unless it blocks the task).
6. **When something is ambiguous**, choose the option that best serves the player's experience, write the assumption down in the task report, and keep going. Don't stall.

---

## 1. Skills: how to use `SKILLS/`

The `SKILLS/` folder contains seven skill documents. **Read every one of them in full before starting Task 1.** They are your quality bar, your vocabulary, and your checklists. They are not optional flavour.

| Skill file | What it governs in this pass |
|---|---|
| `Game Design Mastermind` | Final judgment calls: pacing, "does this make sense to the player", narrative coherence of voice lines, what to cut. Use it as the arbiter whenever two skills disagree. |
| `Gameplay Mechanics Engineer` | Voice/radio trigger logic, cutscene gating, the shared camera helper, mission-state & fail-screen plumbing, weapon anchoring math. |
| `Animation and Game Feel Specialist` | Camera feel (ease, deadzone, lookahead, shake), KRAP Depot cutscene timing and staging, weapon/hand attachment, radio UI motion (slide, fade, typewriter rhythm). |
| `Game Graphics Art Director` | Visual coherence: uniform colours, radio UI look, sprite house style, palette lock, the Print Works interior mood. |
| `create-beautiful-pygame-graphics` | Concrete pygame techniques for the radio UI, sprite generation, layering, glow, dithering, outlines, anti-aliasing tricks. |
| `Game Asset Creator` | The procedural → sprite generator scripts: atlases, metadata, determinism, naming, export pipeline. |
| `World and Level Designer` | KRAP Depot blocking and set dressing, MAG Print Works interior layout, readability of spaces. |

**Rules for using skills:**
- At the top of each task report, list the skill(s) you applied and **one concrete thing each skill made you do differently**.
- If a skill prescribes a checklist, run it and paste the ticked checklist into the report.
- If a skill's advice conflicts with `AGENTS.md`, `AGENTS.md` wins (it encodes hard technical constraints).

---

## 2. Orientation: what you must read before Task 1

Read (don't skim) in this order:

1. `AGENTS.md`
2. All seven files in `SKILLS/`
3. `README.md`, `MEMORY.md`, `FIXES.md`, `IMPLEMENTED.md`
4. `MISSION5_W1_README.txt` … `MISSION5_W7_README.txt` (the M5 build history: why things are the way they are)
5. `RESUME_PROMPT.txt` (previous agent context)
6. `Missing_voice_lines_by_character.xlsx` (which lines have no audio)
7. The character/voice-name mapping files at the repo root: `Bodi = Vasile.txt`, `Enzo = narator.txt`, `Fisherman = Milo.txt`, `Iapteus = Volkov.txt`, `Vasile = Gero.txt`. **Important:** the voice folders under `assets/voice/` use some legacy names (`Vasile`, `Old Fisherman`, `Narrator`, `Balaceanu`, `Darius`, `Gabi`, `Seby`, `Trailer`, `_radio_cache`). Understand the mapping before you audit lines.
8. `tools/smoke_test.py` (know what's already checked so you can extend it).

Then play (or script-drive) each mission once in a debug run and take a baseline screenshot set: M1, M2, M3, M4, M5 (every M5 stage), walk sim, every cutscene. Save them to `shots/polish_pass/00_baseline/`. You'll diff against these at the end.

---

## 3. Execution order & workflow per task

**Order:** 9 → 8 → 3 → 5 → 4 → 1 → 6 → 10 → 2 → 7.

Why this order: quick, isolated correctness fixes first (9, 8), then shared systems that later tasks depend on (camera, uniform colour, weapon anchoring), then the voice pass (it needs the cutscene gate and informs the radio UI), then the radio UI, then the two M5 cutscene jobs, and finally the large sprite effort (it touches the most files, so it goes last on a stable base).

**Per-task workflow (repeat for every task):**

1. **Reproduce.** Get the bug on screen or in a log. Screenshot it.
2. **Locate.** Use the file map in this doc as a starting point, then confirm with `Select-String`. Read the owner module *and* its facade before editing.
3. **Diagnose.** Write the root cause in one or two sentences. If you can't, you're not ready to edit.
4. **Plan.** List the files you'll touch and why. Check import order.
5. **Implement.** Smallest correct change, consistent with the surrounding style.
6. **Verify.** Smoke test + compileall (+ engine3d_check if relevant). Repro steps again → bug gone. After screenshots.
7. **Guard.** Add a smoke check, audit script, or assertion so the bug can't silently come back.
8. **Report.** Append to the running report (see [Deliverables](#deliverables--final-report-format)).

---

## Task 1 — The gigantic voice-line pass

### The problem
Voice and radio lines sometimes trigger when they shouldn't (e.g. a radio line plays while you're in a cutscene, which makes no sense), sometimes might not trigger when they should, and sometimes might not fit the moment (wrong stage, out-of-date info, repeated on reload). We want **every single line** to fire at the right time, in the right context, once, with correct audio and subtitles.

### Where it lives
- `src/audio/voice.py`: voice index & lookup (`_build_index`, `find_line(speaker, text)`, `_split_speaker`, `_norm`, `_scan_files`, `_duration`), `play_line(...)`, `RADIO_STATIC_UNDER_VO`.
- `src/audio/voice_manifest.py`: the line manifest.
- `src/core/interactions.py`: the radio channel.
  - `_radio_release(text, color, duration)`: plays VO via `voice.play_line(None, text, radio=True)`, adds static, schedules typing ticks, and pushes a `"pin"` entry into `STATE.floating_texts`.
  - `trigger_radio_chatter(text, color, duration, priority=0)`: enqueues (drops oldest priority-0 line when the queue is full).
  - `pump_radio()`: releases one line per frame when the channel is free (`_radio_live_until`).
  - `clear_radio_queue()`: already exists and is meant for cutscene takeovers, **but it's only called in some places**, and nothing stops `pump_radio()` from releasing lines *during* a cutscene.
- Call sites (non-exhaustive, find them all): `src/app.py`, `src/missions/m1/*`, `src/missions/m2/*` (incl. `sniper3d.py`), `src/missions/m3/*` (incl. `interrog.py`, `flow.py`), `src/missions/m4/flow.py`, `src/missions/m5/flow.py`, `src/missions/walking_sim.py`, `src/ui/upload_os.py`, every `src/cutscenes/*.py`.

### Step 1: Build the audit tool
Create `tools/voice_audit.py`. It must statically (AST + regex) and, where possible, dynamically enumerate **every** line trigger and output `validation/voice_audit.md` and `validation/voice_audit.csv` with these columns:

| Column | Meaning |
|---|---|
| `id` | Stable ID (`m5_flow_0142` style). |
| `file:line` | Where it's triggered. |
| `channel` | `radio` / `dialogue` / `bark` / `cutscene_vo` / `narrator` / `ui`. |
| `speaker` | Character (normalised through the name-mapping files). |
| `text` | The line text. |
| `mission/stage` | Which mission and which stage/phase can reach it. |
| `condition` | The trigger condition in plain words. |
| `priority` | Radio priority (0 = flavour, higher = critical). |
| `audio` | `found` / `missing` / `mismatch` (via `find_line`, plus a duration sanity check). |
| `once_guard` | Does it have a once-per-run / once-per-checkpoint guard? |
| `can_fire_in_cutscene` | Static guess + dynamic result. |
| `status` | After your pass: `OK` / `FIXED` / `REMOVED` / `MISSING AUDIO` / `NEEDS WRITER`. |
| `notes` | What you changed and why. |

Cross-reference with `Missing_voice_lines_by_character.xlsx`. Every row in that sheet must appear in the audit with a status.

### Step 2: The global "context gate"
Add one authoritative function, e.g. `core.interactions.radio_allowed() -> bool`, that returns `False` while any of these are active:
- any cutscene (2D `cutscenes/engine.py` scenes, all 3D cinematics in `cutscenes/*3d.py`, `m5mid3d` M5X scenes, `m5martial*`, `route12`, `m3*`, `m4aftermath`, `oil_rig_3d`),
- a cinematic handoff pending (see `missions/m5/systems.py` around the "freeze combat while the cinematic handoff is pending" branch),
- an on-screen dialogue box / interrogation dialogue,
- Mission Failed / Mission Complete / death screens,
- pause menu, settings, shop, loading/fade transitions, mission select.

Then:
- In `pump_radio()`, if `not radio_allowed()`: **hold** queued lines with `priority > 0` (story-critical) and **drop** `priority == 0` flavour lines. Held lines resume after the block ends, with a short breath (≈600–900 ms) before the first one.
- If a line is *live* when a cutscene starts: stop the VO with a quick fade (≈120 ms) and a squelch-out SFX, and hide its UI. Don't leave half-typed text on screen.
- Call `clear_radio_queue()` (or the new hold-aware variant) at **every** cutscene entry point. Find them all; don't rely on memory.
- Make sure `_radio_live_until` uses a clock that doesn't run during pause (or explicitly offset it), so pausing mid-line doesn't break the channel.

### Step 3: Make every line make sense
For each audited line, play the game to its trigger (or script-jump with `core/dev_jumps.py`) and confirm:
- **Right moment:** it describes what's true *now*. No "head to the depot" once you're in the depot. No "the door's locked" after it's opened. No warning about enemies who are already dead.
- **Right speaker:** the character is alive, present (or on comms), and would plausibly say it. Check the name mapping.
- **Right mission/stage:** no lines leaking from a previous stage because a flag wasn't reset.
- **Fires once:** no duplicates on checkpoint reload, respawn, re-entering a trigger zone, or alt-tab. Add `once` guards keyed by line id + checkpoint id.
- **No collisions:** two critical lines shouldn't stack. Use priorities sensibly; re-tier lines if needed.
- **Audio = text:** the subtitle text matches what the actor actually says. If it doesn't, update the text to match the audio (the audio is the expensive part). If audio is missing, mark `MISSING AUDIO` and make sure the text-only fallback still reads well and holds on screen long enough (≈ 55 ms per character, min 2.2 s).
- **Timing:** subtitle duration follows `voice._duration(path)` + a tail, not a hard-coded constant.

### Step 4: Guards
- Add a smoke check: start a cutscene, push a radio line, pump N frames, assert nothing was released and nothing is drawn; end the cutscene, assert the critical line releases.
- Add a smoke check that every manifest entry resolves (or is listed as known-missing).

### Definition of done
- `validation/voice_audit.md` exists, every row has a final status, and there are zero rows with `can_fire_in_cutscene = yes` unless they're intentionally diegetic (and documented).
- No radio line can be heard or seen during any cutscene, dialogue, or menu.
- Full play of M1–M5: no out-of-context, duplicated, or orphaned lines.

---

## Task 2 — M5 KRAP Depot cutscene rework

### The problem
The KRAP Depot sequence in M5 feels awkward. **Only this part needs work.** Don't redesign the other M5 cutscenes.

### Where it lives
- `src/cutscenes/m5mid3d.py`:
  - `_depot_set(r, t, bench=True)` (~line 518): the old KRAP depot locker room, mid-repaint (KRAP blue going under Guard colours).
  - `_BOARD = (-2.8, 1.55, 2.86)`: notice-board centre on the back wall.
  - Shots using it (~lines 574–960), tagged `KRAP DEPOT // DECREE No. 1`, `KRAP DEPOT // NOW PRESIDENTIAL GUARD`, `KRAP DEPOT // ISSUE: PRESIDENTIAL BLACK`, and related scenes in the `M5X_SCENES` registry (`m5x_decree`, `m5x_barracks`, `m5x_squadmate`, `m5x_change`, …).
  - Shared helpers: `_shot(...)`, `_person(...)`, pose dicts `_TALK`, `_LEAN`, `_IDLE`, `_rack(...)`, `_dec`, `_add`, `_spr`.
- `src/core/outfits.py`: the `m5x_change` story beat (Biribel tears the KRAP-blue patch off the old vest and presses it onto the new black one, leaves the Guard helmet).
- `src/cutscenes/m5fx3d.py`, `src/cutscenes/m5decal.py`: effects and decals.

### Step 1: Diagnose the awkwardness (write it down)
Watch the sequence 3+ times (both renderers). Produce a shot-by-shot table: shot name, duration, camera position/target/FOV, who's in frame, what's said, what's *wrong*. Look specifically for:
- dead air (holds with nothing happening, or lines ending long before the cut),
- stiff or identical poses (everyone in `_IDLE`, standing in a row facing camera),
- framing problems (heads cut, too much empty wall, the board unreadable),
- crossing the 180° line between shots, jump cuts with near-identical framing,
- camera moves with no motivation, or no movement at all for long stretches,
- unclear story beat (does the player understand KRAP has been absorbed into the Presidential Guard and Biribel is being re-issued?),
- timing out of sync with VO (after Task 1, VO durations are reliable — use them),
- the patch-tearing moment not landing.

### Step 2: Re-stage
Write a new shot list before coding (put it in the report). Aim for a clear arc: **establish** the depot being repainted → **decree** read/pinned on the board → **reaction** from Biribel and squad → **the change** (the patch moment as the emotional payoff, with a close-up and a beat of silence) → **exit** into gameplay.

Techniques to use (from the Animation & Game Feel and World & Level Designer skills):
- Motivated camera: slow push-ins on decisions, a rack focus to the board, an over-the-shoulder reverse for dialogue, a held close-up for the patch.
- Respect screen direction across cuts.
- Vary poses and add small secondary motion (head turns, weight shifts, a hand on the locker, someone pausing mid-repaint). Add new pose dicts if needed; keep them near `_TALK`/`_LEAN`/`_IDLE`.
- Use the set: paint rollers, half-painted lockers, drop cloths, the board as a focal point, light from the doorway. Make the "blue going under red/black" visually readable.
- Cut on action or on the end of a line, never mid-word.
- Keep total runtime similar or shorter. Tighter beats > longer scenes.

### Constraints
- Keep scene keys and their registration in `M5X_SCENES` stable (mission flow calls them by name).
- **Careful:** `_shot` uses `len(tag)` to seed handheld drift and the night sky. If you change or remove tags (see Task 8), keep the seeds stable by passing an explicit seed.
- GL vs software parity: `python tools/engine3d_check.py --shots`.

### Definition of done
- Shot list + before/after contact sheets in the report.
- The sequence reads clearly without subtitles, the patch beat lands, and there are no awkward holds or jump cuts.

---

## Task 3 — Unify the gameplay camera across all missions

### The problem
The camera in M5 doesn't feel like the camera in the other missions.

### Root cause (confirmed during scoping)
`src/core/camera.py::update_camera(target, map_w, map_h, focus_factor, handheld_jitter_timer, factor_fn, deadzone_px, lookahead, apply_final_clamp)` supports a follow **deadzone** and an aim-direction **lookahead**. Constants: `CAM_EASE_GAMEPLAY = 0.15`, `CAM_EASE_M2 = 0.14`, `CAM_EASE_FOCUS = 0.38`, `CAM_EASE_WALK = 0.15`, `CAM_EASE_M3_BREACH_TRACK = 0.22`, `CAM_DEADZONE_PX = 16.0`, `CAM_LOOKAHEAD_PX = 48.0`, `CAM_LOOKAHEAD_WALK_PX = 40.0`.
- **M1** (`missions/m1/update.py` ~467–473) passes `deadzone_px=CAM_DEADZONE_PX` and an aim lookahead.
- **M3** (`missions/m3/interrog.py` ~569–587) does the same (plus a breach-track override).
- **M4** (`missions/m4/systems.py::_update_camera`, ~53–58) and **M5** (`missions/m5/systems.py::_update_camera`, ~52–57, and `missions/m5/flow.py::_snap_camera_safe`, ~52–58) call `update_camera(pos, map_w=w, map_h=h)` with **no deadzone and no lookahead**, so they feel floaty/centred and different.
- M2 has its own deliberate ease and sniper `factor_fn`/jitter.

### What to do
1. Add a single helper in `core/camera.py`, e.g.:
   ```python
   def follow_gameplay(player, map_w, map_h, *, ease=CAM_EASE_GAMEPLAY,
                       lookahead_px=CAM_LOOKAHEAD_PX, deadzone_px=CAM_DEADZONE_PX,
                       aim_angle=None, **overrides):
       ...
   ```
   It computes the aim-direction lookahead (from the player's aim angle, the same math M1/M3 use), applies the deadzone, ease, shake/recoil kick and clamp, and returns what `update_camera` returns.
2. Replace the per-mission follow code in M1, M3, M4, M5 (and the walk sim, using `CAM_LOOKAHEAD_WALK_PX` and movement direction) with the helper. Keep `core/camera.py` free of mission imports.
3. Keep special cases as **explicit overrides**, not forks: M2 sniper (`factor_fn`, `handheld_jitter_timer`), M3 breach track, cutscene focus pulls (`CAM_EASE_FOCUS`, deadzone 0).
4. Stage transitions in M5 (`_snap_camera_safe` after each stage swap at ~251/267/284/325 in `m5/flow.py`): snap correctly with the new helper so there's no lurch on the first frame.
5. Check clamping on every map size (M5 has Guard HQ 30×16, Lower Quarter 40×30, etc.). No black void at edges.

### Definition of done
- Side-by-side clip/screens: M1 vs M5 camera behave the same (same lag, same lookahead when aiming, same deadzone).
- A smoke check asserting every mission's gameplay update goes through `follow_gameplay` (e.g. patch it and count calls over N frames).

---

## Task 4 — Weapon detached from Biribel in the new uniform

### The problem
After Biribel changes into the new KRAP / Presidential Guard uniform, the weapon looks detached from his body.

### Where it lives
- `src/entities/player.py` (~240–250): mission-scoped `story_outfit` (only the M5 draw sets it), resolved roles cached per `(look, outfit)` in `_outfit_rk`.
- `src/core/outfits.py`: `OUTFIT_KRAP = "krap"`, `OUTFIT_GUARD`, `OUTFITS`, the `m5x_change` beat, the KRAP-blue shoulder yoke for gameplay.
- `src/entities/weapon_rig.py`: gun drawing (receiver/handguard quads, barrel, trigger guard).
- `src/core/hands.py`: hand placement.
- `src/missions/m5/draw.py` (~665, ~808) and `src/missions/m5/quarter.py` (~282): where the outfit is applied.
- `src/entities/art_cache.py`, `src/entities/sprite_lib.py`, `src/entities/adornments.py`: cached body renders / overlays.

### Likely causes to check (in order)
1. The outfit render path produces a body surface of a **different size or anchor**, but the weapon is still positioned with the default-body offsets.
2. The outfit cache key is missing the aim angle / weapon id / pose frame, so a stale body is drawn against a live weapon.
3. The shoulder yoke / vest layer is drawn **over** the weapon or hands, visually cutting the connection.
4. Different pivot point (centre vs feet) between the outfit body and the default body.
5. Hands drawn for the default body's arm length.

### What to do
- Find the real cause; fix it at the source (shared anchor data), not with a magic offset.
- Make a debug overlay (toggle via an env var or dev console) that draws the body anchor, shoulder, both hand targets, and the weapon grip point.
- Produce a **verification grid**: 8 directions × {idle, walk, fire, reload} × {default outfit, KRAP, Guard black}. Save it as `shots/polish_pass/04/weapon_grid.png`. The grip must sit in the hands in every cell.

### Definition of done
- Grid shows perfect attachment in every state for every outfit.
- No regression for the default outfit, the shop preview, or the arena.

---

## Task 5 — Biribel renders blue when the uniform is black

### The problem
The new uniform is supposed to be black, but Biribel shows up blue.

### Intended look (per `core/outfits.py` docstring)
- The President's **black** uniform (black beret, no Guard helmet).
- A bright **KRAP-blue chest patch** where Guards carry red.
- In gameplay: a **KRAP-blue shoulder yoke** across both shoulders.
- Everything else black. **Only the patch and yoke are blue.**

### Where to look
`src/core/outfits.py`, `src/core/appearance.py`, `src/core/config.py` (~63), `src/core/state.py` (~265), `src/entities/player.py` (~240), `src/cutscenes/figure_kit.py` (~49), `src/cutscenes/engine.py` (~234), `src/cutscenes/m5martial.py` (~501), `src/cutscenes/m5mid3d.py` (~29, ~408), `src/cutscenes/cast.py`, `src/cutscenes/cast3d.py`, `src/missions/m5/draw.py`, `src/missions/m5/quarter.py`, and the KRAP colour references in `src/missions/m2/draw.py`.

### Likely causes
- The palette **role mapping** for the outfit falls back to the KRAP base palette (blue) for the torso/legs role.
- The 2D gameplay path and the 3D `figure_kit`/`cast3d` path use different outfit definitions.
- A cache keyed only by `look` (not `look + outfit`) serves the old blue render.
- A tint is multiplied on top of black (making it read as dark blue) by night lighting. Check the lighting tint on black materials too.

### What to do
- Define the outfit palette in **one** place and make both 2D and 3D read from it.
- Fix the fallback so unknown roles inherit black for this outfit, not KRAP blue.
- Verify in: gameplay (every M5 stage, day/night/rain lighting), every M5 cutscene after `m5x_change`, the GL and software renderers.
- Before the change beat, Biribel must still be in KRAP blue (don't break continuity).

### Definition of done
- Screenshot set across all of the above showing a black uniform with only the patch/yoke blue.

---

## Task 6 — Radio-line UI: full overhaul

### The problem
The on-screen radio-line UI needs to be better. Overhaul it completely.

### Current state
- `core/interactions.py::_radio_release` pushes a `"pin"` entry into `STATE.floating_texts` anchored near the player.
- `ui/hud.py::draw_pinned_radio(surface, pinned_texts, x=20)` draws it.
- Separate one-off versions exist: `missions/m2/draw.py::_draw_radio_text`, `missions/m2/draw.py::_draw_sniper_subtitles`, `cutscenes/route12.py::draw_ipa_radio_chatter`, `cutscenes/m5martial.py::_draw_m5_radio`, `cutscenes/m3ops.py` (`_draw_m3_volkov_radio_call`, `_draw_m3_radio_recovered`).
- Typing ticks are faked with `audio.schedule(..., "type_tick")`.

### Design brief (apply Art Director + pygame graphics + Game Feel skills)
Build a single `ui/radio.py` (and export it through the `ui` facade in the correct load order) providing a `RadioTransmission` widget used by **all** missions.

**Layout & readability**
- Fixed screen anchor (e.g. lower-left, above the HUD). It must never cover the crosshair, health/ammo, minimap, or objective text. Scale with resolution; test at every supported resolution in `settings.json` / `core/user_settings.py`.
- Max width with clean word-wrapping; max 3 lines visible, older lines scroll up and fade.
- High-contrast text with a subtle backing panel and a 1px outline/shadow. It must stay legible on snow, night, and bright scenes.

**Identity**
- Speaker chip: portrait (sprite from Task 7 if available, otherwise a stylised silhouette) or a callsign plate, with a per-speaker accent colour (reuse/extend `SPEAKER_COLORS` from `cutscenes/engine.py` so colours are consistent game-wide).
- Channel/frequency label (e.g. `KRAP CMD // 141.20`) for flavour, defined per mission.

**Motion & feedback**
- Slide + fade in (~180 ms ease-out), fade out (~250 ms). Squelch-in/out SFX synced to the panel motion.
- Typewriter text paced to VO duration (not a fixed rate) when VO exists; when VO is missing, use a readable fixed rate.
- Live signal meter / waveform driven by the playing VO (amplitude if accessible, otherwise a convincing procedural meter that's only active while VO plays).
- Light static/scanline shimmer on the panel, subtle and not distracting.
- Small "queued" pip showing more transmissions are waiting.
- Critical transmissions get a distinct accent (border pulse once), not a different widget.

**Behaviour**
- Respect `radio_allowed()` from Task 1: hidden instantly (with a quick squelch-out) when a cutscene/menu starts.
- Pauses with the game.
- Accessibility: subtitle size option and an optional speaker-name toggle in settings (hook into existing settings storage).

### Migration
- Route `_radio_release` to the new widget instead of `floating_texts` pins.
- Replace the M2 / route12 / m3ops / m5martial one-offs with the widget **unless** a radio is intentionally diegetic inside a cutscene shot (then keep it, but restyle to match).
- Remove dead code paths once migrated (after confirming nothing else calls them).

### Definition of done
- Mockup screenshots (before/after) in several missions and lighting conditions.
- A smoke check that renders the widget headless with long text, missing VO, and a queued backlog without exceptions.

---

## Task 7 — Procedural art → real sprites (generator scripts)

### The goal
Convert **most** of the game's procedurally drawn graphics into actual sprite assets, produced by **dedicated generator scripts** (Python preferred; another language is fine if it's clearly better for a family). This is a big, deliberate effort. Spend real time on quality.

### Existing pipeline (extend this, don't build a parallel one)
- `src/core/artpack.py`: loaded-sprite registry. **Contract: every getter returns `None` when the PNG is absent, and every call site keeps its procedural renderer as the fallback.** `ACA_ART=legacy` / `ACA_ART=off` force procedural mode.
- `tools/make_art_pack.py`: existing palette-locked, 1:1 house-style author script.
- `assets/art/`, `assets/sprites/`: outputs (bundled by `build.bat`).
- `src/art/m5/*`: per-asset generator modules already in this style (armband, bale, calendar, district_map, guard_banner, guard_plate, hq_locker, m5_guard, mag, mag_icon, maru, plate, portrait_frame, posters, presidential_crest, press, printworks_sign, tram_wreck, wall_posters, `_kit.py`). **Study these first. They're the house style reference.**
- `src/entities/sprite_lib.py`, `src/entities/art_cache.py`: runtime sprite caching.
- `src/cutscenes/m5decal.py`: decals for 3D scenes (baked sprites on quads).

### Step 1: Inventory & ranking
Write `tools/sprites/inventory.py` that scans `src/` for procedural drawing (`pygame.draw.*`, `gfxdraw`, surface-building functions) and groups it by visual asset. Heaviest files found during scoping (count of `pygame.draw.` calls):

| File | ≈ draw calls |
|---|---|
| `missions/m3/draw.py` | 1169 |
| `missions/m2/draw.py` | 922 |
| `missions/m4/draw.py` | 357 |
| `missions/walking_sim.py` | 344 |
| `cutscenes/route12.py` | 316 |
| `missions/m3/systems.py` | 288 |
| `cutscenes/m3ops.py` | 226 |
| `missions/m1/draw.py` | 218 |
| `cutscenes/m3cell.py` | 161 |

Rank asset families by **visual impact × frequency on screen**: player/NPC/enemy bodies → weapons & muzzle FX → environment props (crates, barrels, vehicles, furniture, terminals) → floor/wall tiles & trims → decals (posters, graffiti, blood, scorch) → UI icons/portraits → cutscene props/backdrops. Output `validation/sprite_inventory.md` with the ranked list and a target status for each.

**Target: convert the top-ranked families until at least ~70% of the on-screen procedural art (by the inventory's weighting) is sprite-backed.** Everything you don't convert gets listed with a reason.

### Step 2: Generators
For each family, a dedicated script `tools/sprites/<family>.py` (or extend `src/art/<mission>/` modules where the house pattern already lives). Every generator must:
- Use a **locked shared palette** (`tools/sprites/palette.py`), consistent with `make_art_pack.py`.
- Use a consistent **pixel scale** relative to `TILE_SIZE`, a consistent **light direction** (match the game's top-left key light), consistent **outline** rules (1px darker-hue outline, selective outlining on interior edges).
- Use proper shading: 3–5 tone ramps per material, hue-shifted shadows (cooler) and highlights (warmer), ordered dithering only where it reads well, AO at contact points.
- Produce **all needed frames/directions** (walk cycles, idle breathing, firing, damage flashes, destruction states, door open/close, etc.).
- Export **sprite sheets/atlases** plus JSON metadata: frame rects, anchors/pivots, hand/grip points for characters (feeds Task 4), timings, variants.
- Be **deterministic** (seeded RNG) and re-runnable. Same input → byte-identical output.
- Have a `--preview` flag that writes a contact sheet to `previews/sprites/<family>.png` on light and dark backgrounds.

Add `tools/build_all_sprites.py` that runs every generator in order and fails loudly on errors.

### Step 3: Wiring
- Add artpack getters per family; call sites use the sprite when it's available, otherwise keep the existing procedural code (the contract above). Don't delete procedural renderers in this pass.
- Respect existing draw order and the static layer cache (`core/staticlayer.py`). Bake tiles into the static layer where appropriate for performance.
- Measure FPS before/after in the heaviest scenes; sprites should be equal or faster.

### Quality bar
- Side-by-side comparison per family: procedural vs sprite, in game, same camera.
- Sprites must look like they belong to one game (Art Director skill: silhouette readability at gameplay zoom, value hierarchy: characters > interactables > environment).
- No blurry scaling. Integer scaling only, nearest-neighbour for pixel art.

### Definition of done
- Inventory with statuses, all generators runnable via one command, contact sheets, in-game before/after for every converted family, FPS numbers, `ACA_ART=legacy` still works, smoke test green.

---

## Task 8 — Remove speaker headers from cutscenes

### The problem
In cutscenes there are headers like "VASILE" and "BIRIBEL". Remove them.

### Where they come from (both paths, check both)
1. **2D dialogue box:** `src/cutscenes/engine.py::draw_dialogue_box(surface, speaker, text, char_idx, total_len, can_continue=True)` (~553) draws a header strip (`header_h = 36`) with the speaker name and a `SPEAKER_COLORS` accent (~535, ~598–612).
2. **3D shot tags:** `src/cutscenes/m5mid3d.py::_shot(..., tag="", col=...)` renders a tag label on the shot. At least one shot passes a character name as the tag (`tag="BIRIBEL"`, ~line 1034), and others pass `tag=tag` variables that may hold names (~1006, ~1048). Also check `_tag(...)` helpers in `cutscenes/m3ending.py` (~61), `cutscenes/m4aftermath.py` (~48), `cutscenes/m5martial.py` (~62), and `m5martial3d.py`, `m3*.py`, `route12.py`, `oil_rig_3d.py`, `cast*.py`.

### What to do
- Remove the speaker-name header from the dialogue box everywhere. Shrink the box geometry (`box_h = header_h + num_lines * line_h + bottom_pad`) so it fits the text without an empty band. Keep text wrapping and the continue prompt correct.
- Remove **character-name** tags from 3D shots. **Location/slate tags** (e.g. `LOWER QUARTER // MAG PRINT WORKS`, `KRAP DEPOT // DECREE No. 1`) are a different thing: keep them unless they visibly duplicate a name header. If unsure, list them in the report and ask.
- **Seed stability:** `_shot` seeds handheld drift and the night sky with `len(tag)`. When you blank a tag, add an explicit `seed=` parameter that preserves the old value so the camera motion and sky don't change.
- Speaker readability without names: keep the subtle accent colour bar on the box (from `SPEAKER_COLORS`) so players can still tell who's talking, unless the Art Director pass decides otherwise.

### Definition of done
- Zero character-name headers anywhere in cutscenes (grep for every character name in `tag=` and header renders).
- Before/after screenshots of three dialogue-heavy scenes.

---

## Task 9 — Mission Failed screen always says BLACK NOTEBOOK

### The problem
The Mission Failed screen still says "OPERATION BLACK NOTEBOOK" in later missions. This affects most missions, not just M5.

### Root cause (confirmed during scoping)
`src/ui/system.py` (~1100–1110): the fail screen only special-cases Route 12 (`"OPERATION QUIET ON ROUTE 12 COMPROMISED"` / `"VASILE LINK: LOST..."`) and everything else falls into the `else` branch:
```python
sub_text = "OPERATION BLACK NOTEBOOK COMPROMISED"
flavor_text = "KRAP COMMAND: SIGNAL LOST. DISPATCHING CLEANUP CREW."
```
Meanwhile every mission already sets `STATE.active_mission_operation`:
- M1 `missions/m1/main.py:48` → `"WAREHOUSE RAID - BLACK NOTEBOOK"`
- M2 `missions/m2/starts.py:51` → `"ROUTE 12, QUIET ON ROUTE 12"`
- M3 `missions/m3/flow.py:192` → `"THE STABILIZATION CENTER - THE VOSTRAL"`
- M4 `missions/m4/flow.py:363` → `"THE CAPITAL - 48H CURFEW"`
- M5 `missions/m5/flow.py:342` → `"THE CAPITAL - EMERGENCY RULE"`

Other hard-coded BLACK NOTEBOOK fallbacks to review: `src/app.py:3306` and `src/ui/system.py:872` (`getattr(..., "active_mission_operation", "WAREHOUSE RAID - BLACK NOTEBOOK")`), `src/core/save_system.py:25`, `src/ui/hud.py:647` (dossier header, may be legitimately M1-only), `src/cutscenes/engine.py:786` (M1 intro card, legit).

### What to do
- Create a per-mission table (e.g. in `core/config.py` or a new `core/mission_meta.py` with no game imports) holding: operation display name, failure subtitle, failure flavour line (written in each mission's voice: KRAP command for M1, Vasile link for M2, stabilization-center comms for M3, curfew/capital for M4, emergency rule/Presidential Guard for M5, plus walk sim and arena if they can fail).
- The fail screen reads the current mission from state and looks up the table. If unknown, show a **neutral** fallback (`"OPERATION COMPROMISED"`), never M1's name.
- Fix the `getattr` fallbacks to neutral defaults.
- Make sure the state resets correctly on retry, on checkpoint restore, on returning to the menu, and on mission select / dev jumps, so no stale operation name carries over.
- Write the flavour lines to match each mission's story (read the mission READMEs and cutscene text first).

### Definition of done
- A smoke check that, for every mission, sets up the mission, forces failure, and asserts the fail-screen text matches that mission's table entry.
- Screenshots of the fail screen in M1–M5.

---

## Task 10 — MAG Print Works door: the interior isn't there

### The problem
In the cutscene where Biribel arrives at the MAG Print Works, when the door opens, the interior… isn't. You see the door/shutter go up and there's no real room behind it.

### Where it lives
- `src/cutscenes/m5mid3d.py`:
  - Scene keys `m5x_pw_arrival_wide` → `_arrival_wide` and `m5x_pw_arrival_door` → `_arrival_door` (registered ~line 1252).
  - `_street_set(r, t)` (~47): the Lower Quarter street and the four-storey Print Works facade (note the comments about the near-clipped facade face and the loading door at `abs(px) < 2.4`; facade plane at z ≈ 9.6).
  - `_arrival_door(surface, t)` (~964): the shutter rises 2.4 m over ~3.2 s.
  - `_press_set(r, t, alarm, door)` (~164): the real print-works interior (presses, paper stacks, hanging bulb, type cases, drying line with posters, Maru's table), used later for the back office / breach scenes.

### Root cause (confirmed during scoping)
In `_arrival_door`, the "interior" is **not geometry**. It's a few flat emissive boxes 5 cm thick sitting on the facade plane (`center=(..., 9.60–9.64)`): one orange "lit interior" card, a floor-glow strip, and two pallet silhouettes painted onto the same plane. There's no room volume behind the door, so when the shutter lifts you see a flat glowing card with no depth, no parallax, no light falloff and no inside.

### What to do
1. **Build a real interior volume behind the loading door** (z > 9.6 into the building): floor, side walls, back wall, ceiling, at least 6–10 m deep so the camera's push-in (`cam z 5.9 → 6.2`) and the FOV-58 shot show parallax.
2. **Dress it** to match the established press hall in `_press_set` (World & Level Designer skill: continuity of space). Paper pallets/stacks on the floor, a press silhouette deeper in, hanging work lights, a drying line with posters, ink drums, and the warm bulb tint (`(255, 200–240, 140–210)`). Reuse decals (`_decal.add(r, "posters", ...)`) and the `art.m5.press` sprite where possible.
3. **Light it properly:** warm interior light spilling *out* onto the wet street. Grow the floor light pool on the pavement as the shutter rises (tie it to `h`), add a light shaft with dust motes (`_fx.dust_motes`, `_fx.glow`) and rim light on Biribel. Make the interior slightly brighter than the street so it reads as the focus.
4. **Reveal the interior physically:** the interior must be occluded by the shutter geometry, not clipped by hand-sized boxes (`ph = min(1.1, h)` hacks go away). Make sure the facade has an actual opening (no wall face drawn across the doorway) and that the shutter slats roll up into a housing.
5. **Optional but good:** a silhouette of a printer/worker inside who reacts (looks up) as the shutter rises, to sell that the place is alive. Coordinate with the M5 story (who is inside at this beat?).
6. **Continuity:** the following scenes (back office / `_press_set`) should feel like the same building. Match palettes, props and lighting.
7. **Both backends:** check GL and software. Watch for the near-plane clipping issue noted in `_street_set` comments, painter-layer ordering (`_dec(..., bias)` values) and fog (`_night_street` fog 16–52 m; interior fog should be warmer and closer).

### Definition of done
- Frame grabs at shutter 0%, 30%, 60%, 100% (before/after) showing a real, lit, deep interior with parallax.
- `python tools/engine3d_check.py --shots` parity is fine for this scene.

---

## Cross-cutting QA checklist

Run this at the very end (and paste the ticked list into the report):

- [ ] `python tools/smoke_test.py` → `SMOKE TEST: OK`
- [ ] `python -m compileall -q src` → silent
- [ ] `python tools/engine3d_check.py` (+ `--shots`) → parity OK
- [ ] `python tools/build_all_sprites.py` → succeeds, deterministic (run twice, hash outputs, identical)
- [ ] `python tools/voice_audit.py` → no rows with `can_fire_in_cutscene = yes` (except documented diegetic ones)
- [ ] `ACA_ART=legacy` run → game still fully playable with procedural art
- [ ] `ACARISTAN_RENDERER=software` run → all cutscenes still render
- [ ] Full playthrough M1 → M5 + walk sim: no out-of-context voice lines, no radio during cutscenes, same camera feel everywhere, correct fail screen text per mission, no name headers in cutscenes, black uniform after `m5x_change`, weapon attached in all states, Print Works interior present, KRAP Depot sequence reads well
- [ ] Checkpoint reload in each mission: no duplicated lines, correct fail text, correct outfit, camera snaps cleanly
- [ ] Multiplayer / arena / shop previews unaffected (outfit + camera + radio changes)
- [ ] `build.bat` packaging still includes new assets (`assets/` tree)
- [ ] FPS in the heaviest scenes is equal or better than baseline

---

## Deliverables & final report format

Create `handoff/POLISH_PASS_REPORT.md` and update it as you go. For **each task**:

```
### Task N — <title>
Skills applied: <skill> → <one concrete thing it changed>
Root cause: <1–3 sentences>
Changes: <file list with one-line purpose each>
Guards added: <smoke checks / audit scripts / asserts>
Evidence: <screenshot paths, audit table paths, command outputs>
Assumptions: <anything you decided without asking>
Found, not fixed: <unrelated issues spotted>
```

Also:
- Update `IMPLEMENTED.md` (what's new) and `FIXES.md` (what's fixed).
- Update `MEMORY.md` with any new conventions (shared camera helper, radio gate, radio widget, sprite pipeline, mission meta table) so future agents follow them.
- If you added conventions that belong in `AGENTS.md` (e.g. "all gameplay cameras go through `follow_gameplay`", "never trigger radio without `radio_allowed()`", "all new art via `tools/sprites/` + artpack"), add them there concisely.

---

## Things you must NOT do

- Don't change the runtime map type or bypass `MapBuilder`.
- Don't put logic in facade `__init__.py` files.
- Don't `from owner import mutable_global`.
- Don't switch the display to `pygame.OPENGL` or reach into renderer internals.
- Don't delete procedural fallbacks in Task 7.
- Don't redesign M5 cutscenes other than the KRAP Depot sequence (Task 2) and the Print Works door shot (Task 10).
- Don't rewrite voice line text that has recorded audio to say something the actor didn't say.
- Don't hard-code per-mission strings in UI code. Use the mission meta table.
- Don't ship with the smoke test red, "to fix later".
- Don't commit large binary junk (zips, temp shots) outside the designated folders.

---

## Appendix A — File map cheat-sheet

| Concern | Files |
|---|---|
| Radio channel | `src/core/interactions.py` (`_radio_release`, `trigger_radio_chatter`, `pump_radio`, `clear_radio_queue`) |
| Voice lookup/playback | `src/audio/voice.py`, `src/audio/voice_manifest.py`, `src/audio/audio.py`, `assets/voice/*` |
| Radio UI (old) | `src/ui/hud.py::draw_pinned_radio`, `src/missions/m2/draw.py::_draw_radio_text`, `src/cutscenes/route12.py::draw_ipa_radio_chatter`, `src/cutscenes/m5martial.py::_draw_m5_radio`, `src/cutscenes/m3ops.py` |
| Camera | `src/core/camera.py`; callers in `missions/m1/update.py`, `missions/m3/interrog.py`, `missions/m4/systems.py`, `missions/m5/systems.py`, `missions/m5/flow.py`, `missions/walking_sim.py`, `missions/m2/*` |
| Outfits / colours | `src/core/outfits.py`, `src/core/appearance.py`, `src/core/config.py`, `src/core/state.py`, `src/entities/player.py`, `src/cutscenes/figure_kit.py`, `src/cutscenes/cast3d.py` |
| Weapon attach | `src/entities/weapon_rig.py`, `src/core/hands.py`, `src/entities/player.py`, `src/entities/art_cache.py` |
| M5 cutscenes | `src/cutscenes/m5mid3d.py` (depot, print works, M5X registry), `m5martial.py`, `m5martial3d.py`, `m5studio.py`, `m5fx3d.py`, `m5decal.py` |
| Dialogue box | `src/cutscenes/engine.py::draw_dialogue_box`, `SPEAKER_COLORS` |
| Fail screen | `src/ui/system.py` (~870, ~1075–1110), `src/app.py` (~3306) |
| Mission op names | `missions/m1/main.py:48`, `missions/m2/starts.py:51`, `missions/m3/flow.py:192`, `missions/m4/flow.py:363`, `missions/m5/flow.py:342` |
| Sprite pipeline | `src/core/artpack.py`, `tools/make_art_pack.py`, `src/art/m5/*`, `src/entities/sprite_lib.py`, `assets/art/`, `assets/sprites/` |
| Dev helpers | `src/core/dev_jumps.py`, `src/core/console.py`, `tools/smoke_test.py`, `tools/engine3d_check.py` |

---

## Appendix B — Known facts discovered during scoping

1. **Fail screen:** only Route 12 is special-cased. Everything else prints BLACK NOTEBOOK. `STATE.active_mission_operation` is already set per mission but unused in that branch.
2. **Camera:** M1/M3 use `deadzone_px=CAM_DEADZONE_PX` + aim `lookahead`. M4/M5 don't. That's the "M5 camera feels different" bug.
3. **Radio:** `clear_radio_queue()` exists with a docstring explicitly about cutscenes, but there's no gate in `pump_radio()`, so lines queued or triggered during a cutscene can still play.
4. **Radio display:** radio text is a `"pin"` floating text anchored to the player position, drawn by `draw_pinned_radio`, with several mission-specific copies.
5. **Print Works door:** the interior behind the rising shutter in `_arrival_door` is flat emissive cards on the facade plane (z ≈ 9.60–9.64), with no volume. A full interior already exists in `_press_set` and can be referenced for continuity.
6. **Cutscene names:** speaker headers come from `draw_dialogue_box` (`header_h = 36`) *and* from `_shot(tag=...)` in `m5mid3d.py` (e.g. `tag="BIRIBEL"`). `_shot` seeds handheld drift / sky with `len(tag)`, so keep seeds stable when removing tags.
7. **Outfit intent:** black uniform; KRAP blue only on the chest patch (and gameplay shoulder yoke). Mission-scoped `story_outfit` is set only by M5 draw code; cached by `(look, outfit)`.
8. **Sprite pipeline exists:** artpack registry with `None` fallback, `ACA_ART=legacy`, house-style generators in `src/art/m5/`. The biggest procedural surfaces are `m3/draw.py` and `m2/draw.py`.
9. **Voice assets:** ~225 files under `assets/voice/` in folders `Balaceanu`, `Darius`, `Gabi`, `Narrator`, `Old Fisherman`, `Seby`, `Trailer`, `Vasile`, `_radio_cache`. Character names in code and in folders don't always match (see the `X = Y.txt` mapping files at the repo root).

---

**Start with Section 2 (Orientation). Don't edit a single line of code until you've read `AGENTS.md` and all of `SKILLS/`.**
