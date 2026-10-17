# Mission 3 · Phase 5 — THE KILL ORDER (Slice 5 plan)

Status: **5a-5d BUILT + PLAYABILITY-AUDITED 7/7** (walk-only completion, both branches reach Broadcast) · drafted 2026-09-19 · audited 2026-09-19 · owner: dev + Qwen
Supersedes: the `_start_kill_order_phase()` stub (`missions/m3/interrog.py:77`)
Narrative source: `docs/MISSION3_PLOT.md` beat 5 — *"Survive Balaceanu's
personal security sweep. Alarms trip. IPA sends the disciplined team (M2's
sniper-kill-box discipline, now hunting you in corridors). Set-piece combat.
Volkov's extraction window is closing — he may bail."*

---

## 0. Decisions log (locked this session)

| # | Fork | Decision |
|---|------|----------|
| 1 | Where the fight happens | **New ground-floor map** (`_generate_kill_order_map()`), connected via the existing Archives north stairwell |
| 2 | Volkov's window closes | **Mechanical-light**: he bails → player loses his covering fire at the exfil hold + branch radio/ending text. Same geometry, harder final fight |
| 3 | Sweep feel | **"Most epic" blend**: coordinated role-built fireteams as the core + M2 overwatch pin in the lobby set-piece + breach-charge door blows at crescendo moments + Balaceanu's address as diegetic PA countdown |
| 4 | Build sequencing | **Four sub-slices 5a–5d**, each landing with smoke test + headless E2E green and playable at every step — DONE 2026-09-19 |

Process commitment (carried over from the corpse-variants miss): every
sub-slice starts with a call-site/variant enumeration grep, ends with the
full verification battery (§7), and any new visual FX gets an all-variants
preview render before merge.

---

## 1. Phase flow

```
STAGE_ARCHIVES ──(Vostral acquired + touch north exit)──▶ STAGE_KILL_ORDER
   entry:  _start_kill_order_phase()  (stub replaced by real init)
           - builds kill-order world (stairwell bottom), places player
           - _start_m3_alarm()  (phase-wide; stopped only at exfil)
           - starts STATE.m3_sweep_window (Volkov countdown, §4)
           - opening radio burst + Balaceanu PA beat
   exit:   reach exfil van / dock door cycle completes
           ▶ STATE.request_broadcast_cutscene = True → STAGE_BROADCAST (Slice 6 stub)
```

Flags introduced (all mission-scoped, set in the phase-init function, never
in `STATE.reset()`):

- `m3_sweep_window_frames` — countdown (int frames), paused during
  cutscenes/hit-stop naturally (ticks in `_update_stage` only)
- `m3_sweep_committed` — True once player enters the garage zone (window
  stops mattering; Volkov stays)
- `m3_volkov_bailed` — True when the window hits 0 uncommitted
- `m3_sweep_wave_idx`, `m3_sweep_last_seen`, `m3_sweep_advance_timer` —
  director state (§3)
- `m3_exfil_door_cycle` — holdout timer (§5, beat 3)

Objective string ladder (`_set_objective`, same idiom as Archives):
`"Stairwell down — the sweep is inbound."` → `"Break through the lobby
(marksmen overwatch — stay in cover)."` → `"Loading dock — Volkov's van
(window: M:SS)."` → after commit: `"Hold the dock — door cycles in 0:SS."`
→ bailed variant: `"The van's gone. Dock crane to the roof line — alone."`

---

## 2. Map spec — `_generate_kill_order_map()` (40×40, M3 tile grammar)

One floor below the Archives. Same procedural style/char set as
`_generate_comms_map()` / `_generate_archives_map()`; wall/floor/door/glass
chars reused so all existing render + collision paths apply unchanged.

```
   ┌──────────────────────────────────────────────┐
   │  STAIRWELL TOWER (NW)                          │
   │  · entry from Archives north door (top edge)   │
   │  · switchback descent, first breach-charge     │
   │    set-piece: door below blows on approach     │
   ├──────────┬─────────────────────────┬───────────┤
   │ WEST     │                         │ EAST      │
   │ SERVICE  │      CENTRAL LOBBY      │ SERVICE   │
   │ CORRIDOR │  · 2 sightline lanes    │ CORRIDOR  │
   │ (vert.)  │    (N–S, E–W)           │ (vert.)   │
   │ cover    │  · mezzanine pillars =  │ cover     │
   │ pockets  │    cover pockets        │ pockets   │
   │ + utility│  · MEZZANINE (SE):      │ + utility │
   │ rooms    │    Volkov overwatch /   │ rooms     │
   │ (pickups)│    marksman nest        │ (pickups) │
   ├──────────┴─────────────────────────┴───────────┤
   │  SOUTH CORRIDORS (sweep insertion routes, ×3)  │
   ├────────────────────────────────────────────────┤
   │  LOADING DOCK (S/SE): exfil garage door,       │
   │  crane prop, van spot, roof-line crate stack   │
   └────────────────────────────────────────────────┘
```

Authoring constraints (checked in smoke test):
- every corridor ≥ 3 tiles wide (fireteam formation: shield point + 2 flank)
- ≥ 1 cover pocket per 6 corridor tiles (pin-fairness, §5 beat 2)
- exactly 3 south insertion doorways + 2 breachable shortcut doors
  (west/east utility → lobby) for the anti-turtle flanks
- lobby mezzanine reachable by player (stairs prop) — marksman nest is
  assaultable (epic > frustrating: you can end the pin yourself)
- exfil garage door tile + `_exfil_pos()` marker; dock crate stack blocks
  the "roof line" route until `m3_volkov_bailed` (bailed route dressing)
- beat gates (rush fix 2026-09-27): the lobby→south row (9,10 / 19,20 /
  31,32 on row 27) is sealed until wave 0 clears, the south→dock row
  (6,7 / 19,20 on row 32) until wave 1 clears (`world._KO_BEAT_GATES`);
  the (31,32) dock side door stays owned by the 5d holdout breach

---

## 3. Sweep director ("most epic" blend, core system)

**Roster** (all via `_spawn_m3_guard(..., enemy_type=...)` so stats, gear
overlays and gear-aware corpses apply for free):

| role | count | job |
|------|-------|-----|
| shield | 2 | entry point; holds lanes while team advances |
| breacher | 4 | flank + breach-charge the shortcut doors |
| marksman | 2 | overwatch pin (one active at a time, §5 beat 2) |
| technician | 3 | flush: grenade-less "flush" = breach adjacent doors + radio ping of player pos |
| guard | 9 | line body |

Caps: **≤ 9 concurrent** (director withholds insertions over cap), **~20
total** across the phase. Corpses already cap at 10; particle density and
reduced-motion respected by using `effects.*` helpers exclusively.

**Coordination layer** (cheap, no new pathfinding cost):
- fireteam = leader + members; only the leader runs A* toward
  `STATE.m3_sweep_last_seen`; members target leader pos + formation offset
  (existing `Enemy.update` takes explicit target coords — feed offsets)
- `m3_sweep_last_seen` updates on line-of-sight contact or gunshot hear
  (reuse `enemy_hear_shot`); stale after 6 s → last-seen freezes
- **sweep line**: every 20 s without contact the director advances the
  teams' search target one zone toward the player's zone (zone graph is
  the 6 map zones above) — they hunt you even when you're ghosting
- **anti-turtle**: ≥ 45 s in one zone → breacher pair breach-charges the
  nearest shortcut door (FX: `breach` sound + `effects.shake(18)` +
  `effects.flash`-gated + breach marker; door becomes open rubble)

**Insertion schedule** (crescendo, director-driven not timer-blind):
1. stairwell: 1 shield + 2 guard (beat 1 ambush)
2. lobby approach: marksman #1 takes mezzanine nest + 2 guard south
3. lobby: shield #2 element west corridor + breacher pair east
4. post-lobby: technicians + remaining guards leak in from south ×3
5. holdout: remaining roster on the dock (breach-charge the dock side door)

**Alarm/PA staging**: `_start_m3_alarm()` at init (strobe + loop already
exist); Balaceanu PA beats (§6) interleave with Vasile/Volkov radio; PA
uses `pa_mumble` + `radio_static` bed at low volume so combat audio wins.

---

## 4. Volkov extraction window (mechanical-light)

- `m3_sweep_window_frames = 5 * 60 * 60` (5:00) at phase init; ticks in
  `_update_stage` (so cutscenes/hit-stop don't eat it)
- **commit rule**: entering the dock garage zone (radius check vs
  `_exfil_pos()`) sets `m3_sweep_committed` — the window stops ticking and
  Volkov stays no matter what. The window punishes dallying, not the fight
- thresholds → radio check-ins: **3:30** Volkov idle threat · **2:00**
  Vasile nudge · **0:45** Volkov final warning (lines §6)
- **bail** (window 0, uncommitted): `m3_volkov_bailed = True`,
  `m3_volkov_ally_active = False` with a staged walk-off (Volkov heads to
  the stairwell over 3 s, then despawns with radio line), dock crate stack
  opens the crane/roof-line dressing, Maru ghost-channel becomes the
  diegetic "eyes" support (callout radio on breacher flanks — narrative
  support, no bullets), exfil hold runs **without** covering fire
  (holdout waves unchanged in count, but no suppression on them = harder)
- ending-text hook for Slice 6: `m3_volkov_bailed` readable by the broadcast
  branch epilogues (Branch A/B text can acknowledge it)
- if Volkov is **downed by fire** earlier (existing `m3_volkov_ally_hp`),
  that stays independent: bailed ≠ downed; both remove covering fire but
  only bail flips the epilogue flag

---

## 5. Set-pieces (the epic beats)

**Beat 1 — Stairwell ambush (5a content).** Descent under alarm; scripted
breach-charge blows the door *below* the player on approach (shake + flash
+ debris burst + `breach` sound), shield point steps through the smoke.
Teaches: shields must be flanked/meleed (existing shield arc geometry).

**Beat 2 — Lobby crossfire (5b/5c content).** Marksman #1 pins via a
ported M2 pressure system: `_player_exposed_to_sniper` /
`_player_in_meaningful_cover` generalized to a lane list (N–S, E–W) instead
of a single nest bearing; laser sweep telegraph (port `_add_sniper_laser`
visual, 0.9 s before shots), concrete impacts bracket the player when
exposed. Volkov (if present) suppresses the mezzanine from the west
balcony. Player can assault the nest via mezzanine stairs to end the pin
(reward: marksman corpse + his scope rifle as pickup? — decision: **yes**,
drop `sidearm`-style pickup variant reusing existing pickup kinds only:
mag + bandage; no new weapon ids this slice).

**Beat 3 — Dock holdout (5d content).** Garage door cycles open over 45 s
(`m3_exfil_door_cycle`); remaining roster assaults from 3 directions with
one breach-charge on the dock side door at T+20 s; Volkov covers (or Maru
calls flanks if bailed). Door open + player at van → exfil.

---

## 6. Radio / PA script beats (draft, meta.py idiom)

```
init      VASILE   "Balaceanu signed the kill order on state radio. Every disciplined
                   team in the building is yours now. Stairwell north — I'm moving
                   the van to the loading dock."
init+90   BALACEANU(PA) "Attention. The terrorist Biribel is inside this facility.
                   Security teams: free fire. My address begins at 22:00 — I will
                   not be interrupted."
beat1     VOLKOV   "Through that smoke, friend. Shield first — go around his sight."
3:30      VOLKOV   "Window's closing. My engine idles for no one — not even you."
2:00      VASILE   "Volkov's patience is a resource. Spend it wisely."
0:45      VOLKOV   "Forty-five seconds. Then I'm a memory."
bail      VOLKOV   "...The van's gone. Dock crane, roof line — you're resourceful.
                   Sorry, friend."
bail+60   MARU     "I have eyes on their comms now. I will be your eyes instead.
                   Left corridor — two signatures, shield among them."
commit    VOLKOV   "Behind me. Door cycles in forty-five. I'll keep them off it."
exfil     VASILE   "File's aboard. Drive. DRIVE!"
```

Colors/marks follow `_radio(..., color=C_*, mark=...)` convention; PA beats
use `C_BALACEANU` + `pa_mumble` bed.

---

## 7. Sub-slices + acceptance criteria

**5a — Map & wiring (walkable, no combat).**
`_generate_kill_order_map()` + `_build_kill_order_world()`; real
`_start_kill_order_phase()` (world swap, player place, alarm, flags);
`start_mission3_kill_order_checkpoint()` in `game_core.py` (copy archives
pattern) + console `set_stage kill_order` builds the world (audit: console
sets `mission3_stage` correctly today, but the world must exist);
Archives→KO transition keeps Vostral/pickup state.
*Accept:* headless walk stairwell→dock; smoke OK; E2E transition from
archives checkpoint; no enemies spawn yet; objective ladder line 1.

**5b — Sweep director + alarm/PA + radio.** Director §3 (schedule, caps,
sweep line, anti-turtle breach), alarm start/stop, §6 radio beats init/PA/
beat1, all five roles visible with gear; **all-types corpse preview
re-render** (includes breach-charge FX frames).
*Accept:* concurrent cap holds under console `spawn_enemy` spam; breach
flank triggers on 45 s turtle; every role kill → gear-correct corpse;
smoke + E2E: clear wave 1–3 via checkpoint.

**5c — Overwatch pin + Volkov window.** Lane-based pressure port + laser
telegraph + mezzanine assault path; window countdown + thresholds + commit
rule + bail branch (walk-off, Maru fallback radio, dock dressing swap).
*Accept:* exposed-in-lobby → suppression within 2 s; in-cover → no shots;
bail path E2E (idle 5 min at checkpoint → Maru support live, no Volkov at
dock); commit path E2E (enter dock at 4:50 → window freezes).

**5d — Holdout + exfil + hardening.** Door cycle, 3-direction assault +
dock breach, exfil → `request_broadcast_cutscene` flag → Broadcast stub;
balance pass (player loadout: pistol/os12/k9_smg vs roster); full battery.
*Accept:* both branches (Volkov / bailed) complete headless E2E to the
broadcast flag; perf profile ≤ baseline frame time +8 % with 9 enemies +
10 corpses; smoke OK; worklog entry + this doc updated to BUILT.

**Verification battery per sub-slice** (the discipline from the corpse
miss): (1) variant/call-site enumeration grep for whatever the sub-slice
touches; (2) `tools/smoke_test.py` green; (3) headless E2E through real
`game_update`/`game_draw` for every new path; (4) all-variants preview
render for any new FX; (5) settings interplay check (`particle_density`,
`reduced_motion`) via helpers only; (6) docs/worklog.md entry.

---

## Difficulty & pin honesty (2026-09-19 pass)

- Marksman pin is visually honest: he steps to the mezzanine doorway to paint
  you and withdraws when you break lane/cover; laser/muzzle/LOS = his body.
- ROLE_TUNING table in sweep.py (hp/cooldown/damage per role); staged 24-tick
  insertions; cover/off-sightline spawn tiles; entries seed last-seen.
- Sweep-line 15s, anti-turtle 35s, tighter wave cadence.
- Archives -> KO now hands off through an in-engine cutscene
  (STAGE_KO_TRANSITION + ko_transition_shots); dev entries skip it.

## Dev entry points (Slice 5)

- **CLI boot flag:** `python acaristan.py --dev-mission3-kill-order`
  (aliases `--m3-kill-order`, `--m3-part5`, `--dev-m3-part5`, `--m3-phase5`) —
  straight into the phase with Vostral flag, K-9 loadout and Volkov ally.
- **In-game console:** `set_stage kill_order` during any M3 session (world
  auto-builds on the next tick); combine with `godmode`, `teleport X Y`,
  `spawn_enemy`, `give_ammo`, `heal`.
- **Code/tests:** `game_core.start_mission3_kill_order_checkpoint()`.
- **Tools:** `src/tools/ko_playability_audit.py` (7-check playability audit),
  `render_ko_video.py` at repo root (headless bot preview MP4),
  `src/tools/smoke_test.py` (includes KO walk + wave-insertion checks).

## 8. Risks & mitigations

| risk | mitigation |
|------|------------|
| 9 enemies × A* on 40×40 | leader-only pathing + offset followers (§3); existing 2000-node cap |
| pin feels unfair | laser telegraph 0.9 s, cover-pocket density rule (§2), assaultable nest |
| bail feels punitive | 5:00 window vs ~3 min intended pace; commit rule; Maru fallback support |
| soft-lock at exfil | door cycle is timer-driven, independent of wave state |
| soft-lock at a beat gate | gates blow only on wave-clear; a member wedged on geometry re-inserts near the player after ~10s still (`sweep._update_stuck`); checkpoint reload re-seals gates |
| scope creep into Broadcast | exfil only sets the cutscene flag; Slice 6 owns everything after |
| save/load mid-phase | no mid-mission saves exist today; checkpoint loader is the dev/test path (note in worklog) |

## 9. Out of scope (Slice 5)

Broadcast/studio (Slice 6) · cinematic art pass (deferred per plot-doc
convention) · new enemy roles or weapon ids · K-9 as entity (it's a gun :) )
· multiplayer · achievement/stat hooks beyond `hostiles_killed`.
