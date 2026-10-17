# PLAN_2_EDITOR — Trailer Overhaul EDL (58s Locked)

## 0. Lock
- Runtime: 58.0s, 24 shots. No shot >2.8s pre-0:35. No shot >0.9s 0:35-0:50.
- Aspect: 16:9 master, 2.35:1 letterbox on S01/S02/S04/S10/S22 only. Deliver 16:9 + 9:16 + 1:1.
- Audio ref: 140 BPM pulse. 2-pop 8 frames before 0:00.
- Rule: Zero bot idle on screen. IN on peak, OUT before decay.

## 1. EDL — Second-by-Second Cut List

### HOOK 0:00-0:08
- 0:00-0:02 S01 BLACK CELL | SRC: M3 `cell_ceiling` | IN: fade from black, fluorescent flicker | OUT: hard cut | VO: Biribel "Three days. Maybe four. Hard to count with the lights."
- 0:02-0:04 S02 MONITOR TAUNT | SRC: M3 `interrogation_room` monitor, 130% punch | CRT scanlines, blinking `STATE ADDRESS — LIVE TONIGHT 22:00` | VO: Balaceanu "You told them I was a coward... Tonight I tell the nation what YOU are."
- 0:04-0:06 S03 TITLE SMASH | GFX: CALL OF ACARISTAN slam | 6f white flash + 10px shake + bass hit
- 0:06-0:08 S04 SNIPER TEASE | SRC: M2 sniper gantry + laser sweep | OUT: freeze 6f on muzzle flash | L3: `ROUTE 12 // 48 HOURS EARLIER` typewriter

### ESCALATION 0:08-0:35
- 0:08-0:10 S05 WAREHOUSE INFIL | SRC: M1 exterior rain | Bot already sprinting mid-frame, 115% speed | OUT on door breach frame
- 0:10-0:12 S06 NOTEBOOK GRAB | SRC: M1 NOTEBOOK_POS desk, tight crop | IN 4f before pickup glint, inspect UI 0.4s max | OUT on doorway muzzle flash, match-cut flash->flash
- 0:12-0:14 S07 VOLKOV RUNS | SRC: M1 Volkov escape + `VASILE: "Volkov escaped!"` radio pinned | Split: Volkov left / Biribel firing right
- 0:14-0:16 S08 CARD 1 | BLACK + gunfire J-cut under | `TACTICAL ESPIONAGE`
- 0:16-0:19 S09 CHECKPOINT | SRC: M2 truck inspection + Gabi/Seby/Darius | Highway walk ramped 300% + MiniMap cutaway 0.4s | OUT on sniper laser ON
- 0:19-0:21 S10 KILL-BOX | SRC: M2 sniper kill-box | 3x 0.6s hits: laser -> muzzle -> helmet-off frame | 12px shake
- 0:21-0:23 S11 CARD 2 | 8f black breath, sniper tail only | `DEEP BEHIND ENEMY LINES`
- 0:23-0:26 S12 TANKER VALVE | SRC: M2 tanker south valve + LED + fuel pool | Hand on valve, prompt 0.3s max, tick starts
- 0:26-0:29 S13 TANKER RUN | SRC: M2 `tanker_run` 7s countdown | Sprint to blast-wall shelter @140% | Show `0:03...0:02`, cut 0.5s before arrival
- 0:29-0:32 S14 IPA REVEAL | SRC: M2 authored IPA team | 4x 0.4s: IN on flash, OUT on casing. No reloads.
- 0:32-0:35 S15 CARD 3 | Slow push burning tanker + gantry, music ducks, heartbeat | `FRAMED. HUNTED. DISAVOWED.`

### CLIMAX & DROP 0:35-0:50
- 0:35-0:37 S16 TANKER BLAST | SRC: M2 `_explode_tanker` + charred IPA truck | 4f white-orange flash, shake 18px decay 20f, 40% slow-mo 0.6s then snap | BEAT DROP
- 0:37-0:39 S17 BLACKOUT CUT | SRC: M2 `route12_black` -> M3 cell door kick match-cut | Orange fire -> fluorescent white | SFX: blast tail -> radio static
- 0:39-0:41 S18 BREAKOUT | SRC: M3 Phase2 shiv -> takedown -> sidearm | 3 jump cuts, no crafting menu
- 0:41-0:43 S19 ARCHIVES HEIST | SRC: M3 vault racks/cryo/Vostral beacon | Beacon pulse IN, file grab 0.3s, keypad @400%, flash `I forged it.`
- 0:43-0:45 S20 KILL ORDER | SRC: M3 stairwell breach + shield + lobby | Breach below player (smoke+flash), shield through smoke, laser telegraph 0.9s
- 0:45-0:47 S21 DOCK HOLDOUT | SRC: M3 dock van + 45s door cycle + 3-way assault | Van headlights, strobe muzzles, show `Hold the dock — door cycles in 0:SS` 0.5s
- 0:47-0:50 S22 UPLINK RACE | SRC: M3 `broadcast_live` studio + podium + uplink bar | 0.5s intercuts: sprint / Balaceanu / bar fill | END: file slam, FREEZE, bass cut to silence | `SURVIVE THE VOSTRAL` over freeze

### OUTRO 0:50-0:58
- 0:50-0:53 S23 TITLE DROP | BLACK, logo clean | Stamp with gun-cocks: `M1 // BLACK NOTEBOOK` / `M2 // QUIET ON ROUTE 12` / `M3 // THE VOSTRAL` / tag: `Every rumor has a record.`
- 0:53-0:58 S24 CTA | Triptych 20%: warehouse rain + toll plaza + vault, slow drift | `WISHLIST ON STEAM` + `Top-Down Retro Tactical Shooter` | Piano + radio click. 6f black out.

## 2. Cutting Strategy — Disguise Bot
1. Muzzle-flash cutting: IN 4-6f before flash/kick/glint/laser-ON. OUT 6-10f after impact. Applies S06/S07/S14/S20/S21.
2. Kill highway dead-zone: any straight walk >1.2s = ramp 280-320% + motion blur, keep 0.7s max. L-cut Vasile VO over ramp. 0.4s MiniMap/objective cutaway. Whip-pan 8f out. Applies S05/S09/S13/M3 corridors.
3. Door breaches: 0.3s @100% hand -> 0.2s @180% kick + 8px shake + breach SFX -> 0.4s @60% slow-mo smoke -> snap 100% on first enemy. Applies M1 doors, M3 stairwell/dock/archives-north.
4. Jump-cut hesitations: spin-scan cut to 2f + whoosh + 105% punch. Loot = glint + popup 6f only. Wall-hug = punch 115% + mirror for reverse angle (only if no text in frame). Next-shot audio J-cut 8f early.
5. Fake coverage: 100% -> 125% punch on kills + 2.5px chroma. Freeze + 40% desat 0.4s on S04/S22. Letterbox only on cinematic shots listed above.
6. Never show: still >0.5s, full reload (show 0.3s, cut on mag-out click), full keypad solve (@400%), backtracking (one-way geography: warehouse->highway->cell->archives->dock->studio), console/debug/FPS.

## 3. Title Cards — Exact Copy
- 0:04-0:06 T1: `CALL OF ACARISTAN` — slam, white + 2px black stroke, track +80
- 0:06-0:08 T1b lower-third typewriter small: `ROUTE 12 // 48 HOURS EARLIER`
- 0:14-0:16 T2: `TACTICAL ESPIONAGE` — J-cut gunfire under, 8f fade
- 0:21-0:23 T3: `DEEP BEHIND ENEMY LINES` — after 8f black breath
- 0:32-0:35 T4: `FRAMED. HUNTED. DISAVOWED.` — 3 stabs x0.8s
- 0:47-0:50 T5: `SURVIVE THE VOSTRAL` — over S22 freeze, do not explain Vostral
- 0:50-0:53 T6: `M1 // BLACK NOTEBOOK` / `M2 // QUIET ON ROUTE 12` / `M3 // THE VOSTRAL` + italic `Every rumor has a record.`
- 0:53-0:58 T7 CTA hold 5s: `WISHLIST ON STEAM` + sub `Top-Down Retro Tactical Shooter`
- Banned: MGS phrasing, Open World, early Vostral reveal.

## 4. Sync Notes — AI-3 Sound
- M-HIT1 0:04.0: 55Hz drop + door sub, duck music -10dB under VO, radio bandpass 800Hz-3kHz + `radio_static` bed.
- M-CUT1 0:08.0: 90->128 BPM filter sweep up + hats in.
- M-BREATH 0:21.0: duck -18dB 8f, leave crack tail + shell tinkle.
- M-TICK 0:23-0:29: valve tick + accelerating beeps + low drone.
- M-DROP 0:35.0: mute all 4f pre-blast, then blast + sub + alarm loop. Sidechain music to kicks 0:35-0:50. No lead melody, percussion+bass+chatter only.
- M-SILENCE 0:50.0: hard cut 6f silence, then piano + radio click.
- M-STAMPS 0:50.5/51.2/51.9: 3x gun-cocks panned L-C-R.
- M-CTA 0:53-0:58: `menu_theme.mp3` motif only here + `pa_mumble` + static at -24dB. Layer real cracks over game blips.

## 5. Sync Notes — AI-4 Polish
- Grade: M1 warm tungsten in / cool night out. M2 wet asphalt + orange tanker + rain. M3 cold fluorescent cell / amber archives / sodium dock. Keep contrast.
- Transitions only: hard cuts + 3 whip-pans (0:08, 0:29, 0:37, 8f directional blur) + 2 white flashes (0:04, 0:35). Fades only 0:00 in / 0:58 out.
- Shake: 4px stamps, 8px breaches, 12px sniper, 18px blast decay 20f. Nothing else.
- Vignette closes 10% during M-TICK. Grain 8% on CTA. Text safe 90%, condensed sans all-caps +80 track, white/2px black.
- Thumbnail: S16 blast frame + logo + `THE VOSTRAL`.
- Vertical 9:16: center punch, keep radio/objective text readable.

## 6. Pickup Captures Needed From AI-1 (clean HUD, 60fps, no debug)
1. M1 notebook grab tight, no UI overlap.
2. M2 valve->shelter sprint one take, no stops.
3. M2 blast wide + charred truck 2s tail.
4. M3 shiv takedown + sidearm back-to-back.
5. M3 stairwell breach with 2s smoke tail.
6. M3 dock 10s with Volkov firing.
