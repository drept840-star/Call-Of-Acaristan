# PLAN_4_VISUALS — Trailer Overhaul (Art Director / Post-Production)

Scope: `tools/render_trailer.py` output only. No gameplay changes.
Gate after implementation: `python tools/render_trailer.py --smoke` + `python tools/smoke_test.py` → `SMOKE TEST: OK`.

## 1. HUD REMOVALS (exact)

### 1.1 Delete trailer-baked dev captions
File: `tools/render_trailer.py:127-134` (`caption()`), `459-468` (`SECTIONS`), all `run_gameplay/run_menu/run_walk` `cap_text` args + `FRAME` caption calls (`362-364, 376-378, 396-397`).
- Delete `caption()` function.
- Delete per-section `cap` strings: `ACT I — BLACK NOTEBOOK // warehouse push`, `ACT II — QUIET ON ROUTE 12 // highway patrol`, `ACT II — SNIPER AMBUSH // Route 12`, `ACT III — THE VOSTRAL // breakout`, `ACT III — COMMS WING // relay hunt`, `ACT III — ARCHIVES // the ledger`, `ACT III — KILL ORDER // lobby pin + exfil`, `CALL OF ACARISTAN // main menu`.
- Result: zero bottom-bar (green mono + orange 3px spine on `H-30`) in any frame.

### 1.2 Delete menu section
File: `tools/render_trailer.py:460` (`("menu", "CALL OF ACARISTAN // main menu", None, 3.0, "menu")`), `372-382` (`run_menu()`), `530-535` menu branch.
- Remove SECTIONS entry, `run_menu()`, menu branch in `main()` loop.
- Rationale: `src/ui/main.py:draw_menu()` leaks `ACTIVE SAVE SLOT`, `v0.1.0 BUILD 4471`, `© RETARDOVICI INC.`, `KRAPNET WIRE` ticker — non-diegetic, kills second 0-5.

### 1.3 Capture rules (choreography, no code change)
Reject any take containing:
- `src/ui/hud.py:1652 draw_objective_panel()` with `[E]` / `(0/3)` / `WASD` text. Allowed objectives only: `SNIPER STILL ACTIVE`, `UPLOAD EVIDENCE — BURN THEM ALL`, `VOSTRAL FILE ACQUIRED`, `SURVIVE THE BLACK LEDGER`.
- `src/ui/hud.py:1708 draw_pinned_radio()` with >1 visible line (`PINNED_RADIO_MAX_VISIBLE=2`).
- `_draw_prompt_tag("[E] TAKE THE VOSTRAL")` (`src/missions/m3/draw.py:3527`), `[ SPACE ] close` (`src/ui/hud.py:503,560,744`), `SPACE TO CONTINUE` (`src/cutscenes/engine.py:543`).
- Reticle in stealth takes: set `SETTINGS.show_crosshair=False` for non-combat captures (`src/ui/hud.py:1580 draw_combat_reticle` gate).
- Minimap (`src/ui/hud.py:16 MiniMap.draw`): exactly ONE 2s hero take per act showing player dot + red dots + viewport box. All other takes: punch-in ≥110% so minimap is cropped out.

## 2. VISUAL POLISH DIFFS

### 2.1 `tools/render_trailer.py` — structural diff
- `card()` (`100-116`): keep Oswald 72 bone `(232,222,190)` on `#040506` + 180px orange rule. Shorten hold: `3.0s → 1.8s` cold-open title, `3.5s → 4.0s + 1.0s fade` end-card. Tag args change: `OFFICIAL TRAILER` → keep; `COMING SOON` → delete (replaced, §4).
- `main()` (`522-525`): replace `black 1.5s → card 3.0s → black 0.8s → menu` with cold open (§3). Add 60-tick pre-roll before each `run_gameplay` (extend existing 5-tick warmup at `541-545`) so first fed frame is mid-action, never spawn idle.
- `run_gameplay()` (`345-369`): add `top_up()` already present; add frame-accurate flash hook: on `weapons.handle_shoot()` burst, bump exposure 110% for 1 frame (edit-side, not game-side).
- `mux_1080p_with_music()` (`483-496`): keep 1920x1080 pad path. Add second export: 9:16 center crop `608x1080` for Shorts/TikTok (gameplay punched to 150%, end-card restacked — §4).

### 2.2 Grade stack (edit-side, order matters)
1. Contrast S-curve + desat greens. Protect `C_PLAYER_SKIN (210,180,140)`, crush `C_BG_GAME (45,42,38)`. Push wing grades from `src/core/lighting.py:35-50` +15%: M1 `warehouse (255,238,210)` warm, M2 `route12 (224,234,248)` cold, M3 `cell (236,240,250)` → `archiv (255,242,220)`.
2. Vignette 35% edge burn, 1.15x ellipse (ref: `src/core/config.py:268 draw_vignette(strength=130)`, `src/ui/main.py:587`).
3. Animated fine grain 8-12% (ref: `GRAIN_VARIANTS` 6-variant / 3-frame cycle `src/app.py:156-163`, `_cb_get_grain()` `src/cutscenes/chair.py:170`).
4. Scanlines (ref: `src/core/config.py:283`, alpha-18 every 4px): gameplay 0-10%, CCTV/terminal/broadcast 100% + roll bar.

### 2.3 Act II CCTV treatment (M2 sniper + tanker only)
- 4:3 center crop with black pillars, overlay `TIMECAM 02 // ROUTE 12 // 02:47` in IBMPlexMono Regular 18 (same as `FONT_CAP`), 1px horizontal jitter every ~20 frames, full scanlines. Source label ref: `KRAP FIELD AUDIO // ROUTE 12` (`src/cutscenes/route12.py:607`).

### 2.4 Shake / zoom map (edit-side punch on 1000x700 source; never exceed 130%)
- Tanker blast: 120% + 6-frame shake + 3-frame white flash + 4-frame `hit_stop` freeze hold (ref: `src/fx/effects.py:92 hit_stop()`, `shake()` max-clamp `:75`).
- Sniper telegraph→shot: hold wide 0.9s (laser legible), hard cut 125% on victim + 2-frame shake (ref: `_draw_sniper_muzzle_flashes` `src/missions/m2/draw.py:1343`, `MUZZLE_FLASH` + `bullet_glow` `src/core/config.py:451,702`).
- Safe 742 / Vostral take: 110% slow push, zero shake, hold `CLASSIFIED` stamp 1.5s (ref: `draw_notebook_inspection` `src/ui/hud.py:569`, `draw_volkov_dossier_overlay` `src/cutscenes/engine.py:567`).
- Kill-order breach: 1.5% 8Hz handheld wobble over native `screen_shake` (ref: `src/core/camera.py:update_camera`, `CAM_EASE 0.14-0.15`).
- Broadcast uplink: lock-off, no motion, scanlines + blinking red `LIVE`.

## 3. INTRO (0:00-0:08, replaces menu)
- `0:00-0:01`: BLACK + typewriter `> KRAPNET TERMINAL v7.2.1` / `> AUTHENTICATING OPERATOR .... OK` (reuse `src/ui/main.py:338 _BOOT_LINES`, tick sfx `_schedule_text_ticks`).
- `0:01-0:03`: hard cut ROUTE 12 BLACK frame + red banner `STATE ADDRESS — LIVE TONIGHT — 22:00` (`src/missions/m3/meta.py:109`).
- `0:03-0:05`: title slam `CALL OF ACARISTAN` (existing `card()` style) + 1-frame muzzle exposure bump.
- `0:05-0:08`: M1 warehouse mid-firefight, moving + shooting on frame 1. No walking, no idle, no exfil wait.

## 4. OUTRO END-CARD (6s + 1s fade, replaces `COMING SOON` card)
- Line 1 (rule): orange 3px, 180px.
- Line 2: `CALL OF ACARISTAN` Oswald 72 bone.
- Line 3: `THE VOSTRAL IS REAL` Plex Mono SemiBold 22 orange `(255,120,0)`.
- Line 4 (largest after title): `[Steam logo white] WISHLIST NOW ON STEAM`.
- Line 5: `COMING 2026 — DEMO AVAILABLE` (never `SOON`; use honest window).
- Line 6: handles in Plex Mono 18 grey (`KRAPNET RELAY 7 // Discord / YouTube / TikTok`).
- BG: slow 8s push on `krap_convoy` or `biribel_arrival` cutscene frame, vignette 180 + grain. No HUD, no captions.
- 9:16 variant: same lines restacked vertically.

## 5. USPs → PROOF SHOTS (shot list for AI-1)
1. Rumor-as-weapon: monitor `ROUTE 12 PERPETRATOR: BIRIBEL` (`src/cutscenes/m3cell.py:591`) → Vostral file close-up → `UPLINK SEVERED`. No gunfire.
2. Stealth-to-assault: sight-cone graze → cut to tanker fireball + tinnitus bar (`src/missions/m2/draw.py:2319`).
3. Faction triangle: `CHECKPOINT 12 // ROUTE 12` sign + poster→graffiti wipe + convoy rain. Faction colors `src/core/config.py:57-62`.
4. Improvised craft: shiv-spark close-up (`_cb_draw_shiv_spark`) + safe 742 + molotov fire zone.
5. Paper trail: notebook `CLASSIFIED` stamp + evidence log + green terminals. Clip-bait: kicking server browser, safe-666 demon caption hijack — bonus Shorts, not main trailer.

## 6. HANDOFF
- AI-1: re-capture per §1.3 + §5, 60-tick pre-roll, one minimap hero per act.
- AI-2: grade §2, CCTV §2.3, shake map §2.4, intro §3, end-card §4 (16:9 + 9:16).
- AI-3: boot ticks, CCTV static bed, gunshot transients on flash frames, broadcast sting → resolve + final radio click on end-card, silence on uplink lock-off.
