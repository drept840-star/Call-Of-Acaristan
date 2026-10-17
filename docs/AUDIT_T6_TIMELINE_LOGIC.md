# AUDIT T6 — Timeline & Scene Queue Analyst

**Mode:** read-only investigation. No source files were modified.
**Scope:** every mechanism in the repo that decides *which* clip plays, *how long* it plays, and *what makes it cut*.

---

## 0. TL;DR

There is **no single timeline system**. There are **five independent ones**, with three different
advance models, and they do not talk to each other:

| # | System | Advance model | Owner |
|---|--------|---------------|-------|
| 1 | Cutscene shot lists (`cutscene1_shots`, `mission2_ending_shots`, …) | **Input-gated** — SPACE only, with a `min_ms` floor. No upper bound. | `src/app.py:388-1996` |
| 2 | In-mission cinematic beats (sniper ambush, flank, evidence card) | **Hardcoded frame counts** (60 fps sim ticks) | `src/missions/m2/sniper.py`, `src/missions/m2/draw.py` |
| 3 | M3 interrogation dialogue beats | **Auto-advance** frame counter (7–12 s), the only self-cutting dialogue in the game | `src/missions/m3/interrog.py:306-322` |
| 4 | M2/M3 stage machines | **Objective completion** (clue count, enemy list, proximity, keypress) | `src/missions/m2/update.py:166-319` |
| 5 | Trailer render pipelines | **Explicit seconds per EDL row**, executed in list order | `tools/render_trailer.py`, `tools/render_trailer_v2.py` |

### The answer to "why did Route 12 / the empty truck repeat 3 times"

`route12_aftermath` is queued **3×** in `mission2_ending_shots` (`src/missions/m2/meta.py:96-163`,
at lines **98, 116, 121**) — the single most-duplicated scene string in the entire codebase:

```
count  scene
   3   route12_aftermath      <-- M2 ending, 3 different labels
   3   title_card
   2   interrogation_room
   2   m3_volkov_gives_mags
   2   route12_broadcast
   2   route12_black
```

It is the **most-duplicated scene in the game and the most visually static of them all**, because:

* `draw_route12_aftermath` (`src/cutscenes/route12.py:1520-1529`) is a **9-line wrapper**:
  `_draw_route12_checkpoint_base(surface, t, tanker=True)` + a fire overlay + one Biribel silhouette.
* `_draw_route12_checkpoint_base` (`route12.py:960-1023`) takes exactly **one** meaningful
  parameter — `tanker: bool`. It has no `variant`, `phase`, `intensity`, or `progress` argument.
  The tanker slab (a rounded rect + red stripe + "LEAKING FUEL" text) is drawn at **hardcoded
  pixel coordinates** with no state input.
* The renderer is called as `draw_cutscene_scene(surface, shot, t)` where
  `t = pygame.time.get_ticks() - cp.start_time` (`src/app.py:1958-1959`) — **elapsed time since
  *this shot* started, reset to 0 on every advance** (`app.py:1916`, `app.py:1891`).

So shots 2 and 3 are not "similar" — they are **frame-for-frame replays of shot 1**, restarted from
`t=0`. Same plate, same truck, same fire, same silhouette, same scroll phase.

The **only** per-shot variation the three rows actually carry is the dialogue string and
`lighting`, and `lighting` is a near no-op here: `draw_cutscene_scene` does
`surface.fill(shot.get("lighting"))` first (`engine.py:22`), but the very next call
`draw_sky_gradient` (`route12.py:962` → `src/core/config.py:145`) overwrites every pixel from
`SCENE_TOP` to `SCENE_BOT`. Only the 80px letterbox bars keep the fill colour — so the three
"visually distinct" rows differ by at most a `(12,10,8)` vs `(10,10,12)` shift in the black bars.

**Net effect:** the M2 finale cuts to the identical empty Route 12 highway three times in a row,
each time with a new speaker label pasted over it:

| idx | scene | speaker | label shown |
|-----|-------|---------|-------------|
| 0 | `route12_aftermath` | SYSTEM | `TRANSMISSION SENT / ARCHIVE PARTIALLY CORRUPTED` |
| 4 | `route12_aftermath` | VASILE | `Biribel... tell me you got out.` |
| 5 | `route12_aftermath` | BIRIBEL | `They framed KRAP.` |

---

## 1. System 1 — Cutscene shot lists (the one the bug lives in)

### 1.1 Data shape

A "clip" is a dict. Canonical keys (`src/app.py:408-414` `_normalize` forces `text` to `""`):

| key | type | read at | meaning |
|-----|------|---------|---------|
| `scene` | str | `engine.py:21` | dispatcher key → a `draw_*` function |
| `speaker` | str\|None | `app.py:1979` | dialogue-box header |
| `text` | str | `app.py:1976` | typewriter body |
| `lighting` | RGB | `app.py:22`→`engine.py:22` | background fill, usually overpainted |
| `min_ms` | int | `app.py:1880, 1973` | **minimum** on-screen time; SPACE is rejected before this |
| `hide_caption` | bool | `app.py:1974` | suppress the dialogue box entirely |
| `hard_cut` | bool | `app.py:1885` | skip the 15-frame fade-out on advance |
| `is_transition` | bool | *never read* | **dead key** (only `meta.py:150` sets it) |

Player state lives on `CutscenePlayer` (`app.py:388-428`): `shots, after_state, use_fades,
shot_idx, char_idx, timer, start_time, transition_timer, fired_cues`.

### 1.2 The cut-to-next-scene rule — verbatim

`src/app.py:1867-1894`:

```python
def handle_event(self, event, mouse_x, mouse_y, keys):
    if event.type != pygame.KEYDOWN or event.key != pygame.K_SPACE:
        return
    ...
    if cp.char_idx < len(shot["text"]):
        cp.char_idx = len(shot["text"])          # 1st SPACE = skip typewriter
    else:
        elapsed_ms = pygame.time.get_ticks() - cp.start_time
        if elapsed_ms < shot.get("min_ms", 0):
            audio.play("menu_hover", volume=0.12)  # "too soon" tell
            return
        if cp.shot_idx < len(cp.shots) - 1:
            if cp.use_fades and not shot.get("hard_cut"):
                cp.transition_timer = 15          # fade out over 15 frames
            else:
                cp.shot_idx += 1; ...             # instant cut
```

**Answer to Task 3:** for System 1 it is **none of tick count, objective completion, or a
hardcoded timer**. It is *player input*, gated by a per-shot `min_ms` **floor** and nothing else.
`_CutsceneState.update` (`app.py:1896-1933`) contains **no** shot-advance branch whatsoever — it
only does SFX cues and the typewriter. Consequence: **a shot with no `min_ms` can be cut after one
SPACE (≈2 frames), and a shot with `min_ms` and no SPACE can sit on screen forever.** There is no
`max_ms` anywhere in the system.

### 1.3 Transition timing (hardcoded frames)

`app.py:1910-1919`:

* `transition_timer = 15` → fade **out**, counting down; at **8** the shot actually swaps
  (`shot_idx += 1`, `char_idx = 0`, `start_time = now`), then `transition_timer = -12` → fade **in**.
* Alpha: `255 * transition_timer/15` out, `255 * (1 - |timer|/12)` in (`app.py:1987-1996`).
* So the visible black frame is `15 - 8 = 7` frames out, then 12 frames in. Hardcoded, not
  `min_ms`-aware.

### 1.4 Audio cues (the one *ms*-driven part of System 1)

`app.py:380-385` + `app.py:1904-1908`:

```python
KO_CUT_CUES = {
    "m3_ko_charge":    ((0, "door_rattle", .35), (1150, "breach", .9)),
    "m3_ko_stairwell": ((0, "concrete_impact", .28),),
    "m3_ko_aperture":  ((0, "elec_hum", .20), (1950, "bullet_snap", .45)),
    "m3_ko_van":       ((0, "door_creak", .40),),
}
...
for ms, name, vol in KO_CUT_CUES.get(shot["scene"], ()):
    if elapsed >= ms and (cp.shot_idx, name) not in cp.fired_cues:
        cp.fired_cues.add((cp.shot_idx, name)); audio.play(name, volume=vol)
```

`fired_cues` is keyed by `(shot_idx, name)`, so a cue at 1150 ms is **guaranteed dead** on any
shot the player cuts before 1.15 s — and `min_ms` is not consulted when scheduling. Only 4 of the
~45 scene IDs have cues at all.

### 1.5 The dispatcher (this is where "which clip" is decided)

`src/cutscenes/engine.py:20-417` — one `if/elif` chain, ~70 branches, `scene` string → draw call.

**Dead branch found:** `engine.py:274-275` handles `scene == "route12_tanker"` →
`draw_route12_tanker` (`route12.py:1174-1175`), which is itself just
`_draw_route12_checkpoint_base(surface, t, tanker=True)`. **No shot list anywhere queues
`route12_tanker`.** A repo-wide search finds the string only in `engine.py:274` and in the two
rain-scene sets in `app.py:1943, 1965`. The branch is unreachable.

That matters for this audit: the *intended* tanker plate and the *actual* aftermath plate are the
**same function with the same argument**. `route12_tanker` was clearly meant to be the
"intact tanker" beat and `route12_aftermath` the "post-blast" beat, but the post-blast variant
adds only a fire overlay and never varies the truck — so the "empty truck" is the *only* truck the
renderer has.

### 1.6 Where each shot list is entered

`app.py:435-438` `start_cutscene(shots, after_state, use_fades=True)` → `gsm.transition("CUTSCENE")`.
Call sites: `app.py:1036, 1091, 1112, 1179, 1198, 1594, 1603, 2042, 2189, 2194, 2199, 2204,
2209, 2219, 2234, 2239, 2244, 2249, 2256, 2515, 2525`. The M2 finale specifically:
`app.py:2187-2191`, gated on `gc.request_mission2_ending` (set by `_complete_mission2`).

---

## 2. System 2 — In-mission cinematic beats (hardcoded frame counts)

### 2.1 M2 sniper ambush — the "12-point rework" beat clock

`src/missions/m2/meta.py:647-687`:

```python
SNIPER_PHASES = [
    {"name": "regroup",        "duration": 100},   # 1.67s
    {"name": "movement_one",   "duration": 720},   # 12.0s
    {"name": "movement_two",   "duration": 600},   # 10.0s
    {"name": "movement_three", "duration": 600},   # 10.0s
]                                                        # total 2020 frames = 33.7s

SNIPER_BEAT_CLOCK = { "regroup": {"spread_line": 80},
                      "movement_one": {"regroup_line":70, "scan_west":170, "gabi_crack":300,
                        "tried_to_save_window_start":320, "tried_to_save_window_end":360,
                        "silence_start":302, "silence_frames":110, "vasile_down":320,
                        "origin_flash":440, "muzzle_flash":440, "gantry_hold":460, "seby_react":660},
                      "movement_two": {...}, "movement_three": {...} }
```

Phase advance (`sniper.py:1131-1133`):

```python
STATE.mission2_sniper_phase_timer = pt + 1
if STATE.mission2_sniper_phase_timer >= _sniper_phase().get("duration", 120):
    _advance_sniper_phase()          # sniper.py:402-408
```

**Events use exact equality, not `>=`** (`meta.py:693-695`):

```python
def _beat_now(phase, pt, event):
    f = SNIPER_BEAT_CLOCK.get(phase, {}).get(event)
    return f is not None and pt == f
```

consumed at `sniper.py:988-1104` (17 call sites). This is frame-exact by design — it is
deterministic in *sim ticks*, not wall time — but it is **not** robust: any path that calls
`_update_sniper_cutscene` zero or two times in a tick (pause, focus loss, a second caller)
silently drops the event forever. `gabi_crack`, `muzzle_flash`, `seby_react`, `darius_crack`
etc. are all one-shot `pt == f` gates.

Two beat keys are **defined but never consumed**: `silence_start` / `silence_frames` (read
nowhere), and `muzzle_flash` (only `origin_flash` is dispatched, `sniper.py:1027`).
`SNIPER_TRY_SAVE_WINDOW_START/END` (`meta.py:331-332`) are documented as "module-level constants
for any code that wants to read them" — the live values come from the beat clock instead.

### 2.2 M2 flank cutscene

`meta.py:444-451` — `FLANK_CUTSCENE_DURATION = 540` (9.0 s) with in-frame beat thresholds at
90 / 180 / 220 / 300 / 330 / 390 / 510. Driven by a **countdown** timer
(`mission2_flank_cutscene_timer` decremented in `_update_flank_cutscene`,
`m2/draw.py:7457-7463`), started at `m2/draw.py:7443`. The post-cutscene stage gate in
`m2/update.py:203-207` explicitly waits for `mission2_flank_cutscene_timer <= 0` — a real
objective/timer interlock, correctly done.

### 2.3 M2 evidence cinematic

`m2/draw.py:3920-3925` + `3933-3990`:

```python
_EVIDENCE_CINEMATIC_SHOTS = [
    {"name": "comms_cut",    "duration": 60},    # 1.0s
    {"name": "evidence_wall","duration": 210},   # 3.5s
    {"name": "vasile_line",  "duration": 180},   # 3.0s
    {"name": "upload_punch", "duration": 90},    # 1.5s
]                                                        # total 540 frames = 9.0s
```

**This is the cleanest timeline in the repo** — pure `duration` list, `>=` comparison, no
equality gates, 0.5 s post-cinematic enemy-freeze grace. It is also the *only* system that keeps
the name "shots" for a list of frame durations. Note the field name collision: here `duration` is
**frames**, in System 1 `min_ms` is **milliseconds**, and in System 5 it is **seconds**. Three
units, one concept.

---

## 3. System 3 — M3 interrogation beats (the only auto-advancing dialogue)

`src/missions/m3/interrog.py:306-322`:

```python
if not _line_fully_typed(beat):
    _m3_flow._post_type_hold = 0
    return
_m3_flow._post_type_hold += 1
if _action_auto_locked(beat):
    return
if _m3_flow._post_type_hold >= _post_type_hold_frames(beat):
    _advance_beat()
```

`_post_type_hold_frames` (`interrog.py:64-74`) = `max(_POST_TYPE_HOLD_MIN, min(_POST_TYPE_HOLD_MAX, n_chars * _POST_TYPE_HOLD_PER_CHAR))`
with `meta.py:387-389`: **MIN 420 (7 s), MAX 720 (12 s), PER_CHAR 8**.
(Stale comment at `interrog.py:308` and `flow.py:127-128` still says "3s floor, 6s ceiling,
~3 frames/char" — the constants were retuned and the prose was not.)

This is a **third** advance model: `STAGE_INTERROGATION` dialogue auto-cuts, while every
`cutscene*_shots` list requires SPACE. Same game, two contradictory interaction contracts.

---

## 4. System 4 — Stage machines (objective completion)

`src/missions/m2/update.py:166-319` `_update_stage(keys)`. Enum at `m2/meta.py:222-232`:

```
investigate → sniper → combat → truck → tanker → tanker_run → blackout → evidence → upload → exfil → done
```

Each transition gate, and what actually drives it:

| transition | gate | model |
|---|---|---|
| investigate → sniper | `clue_count >= 4` **and** `_near(KILL_ZONE, 120)` | objective + proximity |
| sniper → combat | `_update_sniper_sequence` internal | frame clock (§2.1) |
| combat → truck | `post_phase=="done"` **and** `not STATE.enemies` **and** `flank_cutscene_timer<=0` | objective + timer interlock |
| truck → tanker | manifest interact | interact |
| tanker → tanker_run | `mission2_tanker_inspected` | interact |
| tanker_run → blackout | `mission2_countdown <= 0` | hardcoded frame countdown (the 7 s run) |
| blackout → evidence | `mission2_timer >= 210` **and** `not player_dead` | hardcoded frames + card close |
| evidence → upload | `found >= 3` **and** `_near(UPLOAD_TERMINAL_POS, 95)` **and** `keys[K_e]` | objective + proximity + input |
| upload → exfil | `upload_os` completion | sub-state machine |
| exfil → done | `_near(EXFIL_POS, 92)` | proximity |

Note: `MISSION_PHASES` (`m2/meta.py:205-212`, `m3/meta.py:146-153`) is **descriptive only** —
`m3/meta.py:144-145` says so explicitly ("Not the runtime driver — `STATE.mission3_stage` is").
`MISSION_PHASES` is surfaced to menus and nothing else; it is a second, parallel, non-binding
description of the same 6 phases and will silently drift.

---

## 5. System 5 — Trailer render pipelines ("which clips get recorded")

### 5.1 Pipeline A — `tools/render_trailer.py` (default path)

`TOURS` (`render_trailer.py:491-500`) maps a **section key** → `(solid chars, map key, goal list)`:

```python
"m2":       [("C","B","T"), "m2", [(14,72), (22,68), (30,62), (24,58)]],
"m2sniper": [("C","B","T"), "m2", [(48,28), (52,30), (58,28), (50,26)]],
```

`SECTIONS` (`:545-553`) is the clip queue: `(key, starter, seconds, mode)`. 7 sections,
2 of them Route 12 (`m2` 8.0 s, `m2sniper` 7.0 s).

`main()` (`:653-678`) loops it, calling `starter()` (full mission reset) then
`run_gameplay(sec_seconds(secs), make_router(key), fight=True)`. A fresh `Router` is built per
section, so **every take replays the identical goal list from the identical spawn**.

### 5.2 Pipeline B — `tools/render_trailer_v2.py` `EDITOR_EDL` (the 58 s locked cut)

Run only with `ACARISTAN_EDITOR_CUT=1` (`render_trailer_v2.py:620-626`). `EDITOR_EDL`
(`:48-93`) is a 28-row explicit cut list; row kinds: `black | boot | broadcast | card |
game | endcard`. Durations are **seconds**, asserted to sum to 58.0 ± 0.6 (`:622-623`,
`editor_runtime()` at `:107-119`).

**This is the second, larger instance of the same defect.** Row schema is
`(kind, key, starter_name, secs, cap_text)` — **the label is pure decoration**; the *content* is
`key` + `starter_name`. Seven rows carry Route 12:

| row | key | starter | secs | label |
|---|---|---|---|---|
| S04 | `m2sniper` | `start_mission2_sniper` | 2.0 | `ROUTE 12 // 48 HOURS EARLIER` |
| S09 | `m2` | `start_mission2` | 2.6 | `CHECKPOINT // truck inspection` |
| S10 | `m2sniper` | `start_mission2_sniper` | 2.2 | `KILL-BOX // laser to helmet-off` |
| S12 | `m2` | `start_mission2` | 2.5 | `TANKER // hand on valve` |
| S13 | `m2` | `start_mission2` | 2.8 | `TANKER RUN // 0:03 countdown sprint` |
| S14 | `m2` | `start_mission2` | 2.6 | `CONTACT // flash to casing only` |
| S16 | `m2` | `start_mission2` | 2.0 | `BLAST // white-orange flash` |

`m2` is queued **5×** and `m2sniper` **2×**, each with a *different* label. But:

* `start_mission2` resets the mission every time → player always spawns at
  `PLAYER_START = _tc(8,74)` (`m2/meta.py:306`).
* `make_router("m2")` rebuilds the **same** goal list `[(14,72),(22,68),(30,62),(24,58)]`.
* Player `self.speed = 5` px/tick (`entities/player.py:26`), 60 ticks/s. A 2.0–2.8 s take =
  120–168 ticks = **600–840 px = 9–13 tiles**. Goal legs are 6–10 tiles.
* ⇒ **Every `m2` take covers roughly the same first leg and never reaches the second.**
  The tour terminates at tile (24,58), inside the `blast_scene` zone
  (`m2/meta.py:248-253`); the tanker is at `_tc(45,40)` and the IPA truck at `_tc(46,31)` /
  `_tc(8,15)`. **Neither is ever on screen.**

So S09 "truck inspection", S12 "hand on valve", S13 "tanker run", S14 "contact" and S16 "blast" are
all *the same 2.5 s of the player jogging north up the empty west approach road*, re-labelled.
The 3 civilian wrecks that line that road (`m2/world.py:539-543`, at tiles (9,70), (18,60),
(31,57)) are the only thing on camera — an abandoned vehicle, re-shown five times, five labels.
That is the second reading of "the empty truck repeated".

`render_ko_video.py:290` records that this was already known and, for *that* script, fixed:

```python
# ── Scene A: warehouse shootout (no Route 12, no truck, no walking) ──
```

Its header (`:3-4`) states the new rule — *"Combat-only timeline, **zero repeats**"* — and the
printout at `:282-288` hardcodes 3 scenes with distinct maps. **The fix was never applied to
`render_trailer_v2.EDITOR_EDL`**, which still carries the label-only differentiation.

### 5.3 Still-capture shot lists (for completeness)

`tools/render_previews.py:92-98` (`SCENES`, 5 M3 rooms), `tools/golden.py:69-70`
(`SCENES`, 3 M3 rooms), `tools/m3_room_shots.py`, `tools/m2_floor_shots.py`,
`tools/m2_walk_shots.py`, `tools/cursor_arrow_shots.py`, `tools/slot_select_shot.py`,
`tools/render_ko_shots.py`. All are `(name, setup_fn)` tuples rendering **one** still each —
no timing, no repetition risk. `render_previews.py` is the only one that has already been
PLAN_4-cleaned (its old menu capture is gone, replaced by a `menu` still at `:106-109`).

---

## 6. Summary table — what decides "cut to next scene"

| System | Advance trigger | Upper bound on clip length? | Skip allowed? |
|---|---|---|---|
| Cutscene shot lists | `KEYDOWN SPACE` | **No** — unbounded | Yes, instantly, if `elapsed >= min_ms` |
| M2 sniper ambush | frame counter `>= SNIPER_PHASES[i]["duration"]` | Yes (100/720/600/600 f) | No |
| M2 flank | countdown `540 → 0` | Yes (9.0 s) | No |
| M2 evidence card | frame counter `>= shots[i]["duration"]` | Yes (60/210/180/90 f) | No |
| M3 interrogation beats | `post_type_hold >= 420..720` | Yes (7–12 s) | Yes, except `_action_auto_locked` |
| M2/M3 stage machine | objective / proximity / interact | n/a (gameplay) | n/a |
| Trailer EDL | list order | Yes (explicit seconds) | No |

---

## 7. Defects found (no code changed)

| # | Severity | Location | Defect |
|---|----------|----------|--------|
| 1 | **High** | `m2/meta.py:98,116,121` + `route12.py:1520-1529` | `route12_aftermath` queued 3× with 3 labels; renderer is a 1-arg wrapper over a 1-flag base with per-shot `t` reset → **frame-identical replays** |
| 2 | **High** | `route12.py:960-1023` | `_draw_route12_checkpoint_base` has no variant/intensity parameter, so `tanker=True` cannot express "before" vs "after" the blast — the truck is always the same empty slab |
| 3 | **High** | `render_trailer_v2.py:62-75` (`EDITOR_EDL`) | 7 Route 12 rows, 2 distinct tours, labels are the *only* differentiator; 5 identical `m2` takes whose captions describe content the camera never reaches |
| 4 | Med | `engine.py:274-275` | `route12_tanker` dispatcher branch unreachable — no shot list queues it |
| 5 | Med | `app.py:1867-1894` | No `max_ms`. A `min_ms`-less shot is one SPACE from gone; a `min_ms`'d shot with no input never leaves. Contrast M3, which auto-advances. |
| 6 | Med | `meta.py:654-687` | `silence_start` / `silence_frames` / `muzzle_flash` defined in `SNIPER_BEAT_CLOCK`, never dispatched |
| 7 | Med | `sniper.py:988-1104` + `meta.py:693-695` | `_beat_now` uses `pt == f`; any skipped or duplicated tick drops the beat permanently |
| 8 | Med | `app.py:1942-1949` vs `1964-1965` | Two hardcoded rain-scene sets that disagree: `set_ambience` includes `seby_pickup_body/reach/raise`, `render`'s `outdoor_rain` does not → those shots get rain **audio** with no rain **visuals** |
| 9 | Low | `app.py:380-385` + `1904-1908` | `KO_CUT_CUES` schedules at absolute ms with no `min_ms` check; a shot cut early silently loses its 1150 ms / 1950 ms cue |
| 10 | Low | `m2/meta.py:150` | `is_transition` set on the `krap_door_kickin` row, read nowhere |
| 11 | Low | `m2/meta.py:205-212`, `m3/meta.py:146-153` | `MISSION_PHASES` is a non-binding duplicate of the runtime stage enum (`m3/meta.py:144-145` admits this) |
| 12 | Low | `interrog.py:308`, `flow.py:127-128` | Comment says "3s floor, 6s ceiling, ~3 frames/char"; `meta.py:387-389` is now 7 s / 12 s / 8 frames |
| 13 | Low | `m2/draw.py:3921-3924` vs `meta.py:73` vs `render_trailer_v2.py:53` | Three different units for shot duration — **frames**, **milliseconds**, **seconds** — with no shared type or name convention |
| 14 | Low | `engine.py:22` / `config.py:145` | `lighting` is overwritten by every `draw_sky_gradient` caller; it survives only in the 80 px letterbox bars. Effectively a no-op key that reads as meaningful. |

---

## 8. Recommended direction (for the owning agent — not applied)

The single highest-leverage change is to give the shot-list renderer a **variant parameter** and
make the queue carry it, so labels and pictures are bound together:

1. Add `"variant": int|str` (or `"beat":`) to the shot dict, threaded through
   `CutscenePlayer._normalize` → `draw_cutscene_scene` → the `route12_*` renderers, and derive
   the animation phase from the **global** cutscene clock, not per-shot `t`. Two shots with
   different variants then genuinely differ, and one variant repeated three times still reads as
   a deliberate hold.
2. Collapse `mission2_ending_shots[0,4,5]` to **one** `route12_aftermath` row and move the
   "TRANSMISSION SENT" / "tell me you got out" / "They framed KRAP" lines onto distinct plates
   (`route12_black` already exists and is only used twice).
3. In `EDITOR_EDL`, either give the five `m2` rows genuinely different `key`s (new `TOURS`
   entries whose goals reach the truck `(46,31)`, the tanker `(45,40)`, the toll plaza
   `(36,34)`, the control building `(58,18)`) or stop labelling them. `start_mission2_*`
   shortcuts already exist for exactly this (`m2/starts.py:328` `start_mission2_truck`,
   plus the flank/checkpoint/evidence jumps at `:286-413`) — the EDL never uses them.
4. Delete the dead `route12_tanker` branch, or wire it to a shot.
5. Add `max_ms` to `_CutsceneState.handle_event` so no cutscene can soft-lock, and reconcile
   the two rain-scene sets into one constant.
