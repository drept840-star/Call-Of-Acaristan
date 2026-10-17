# PLAN_3_AUDIO — Official 60s Trailer Overhaul (Audio Director)

Status: FINAL PLAN — implementation-ready. No code touched.
Owner: AI 3 (Audio). Consumers: AI 1 (Choreo), AI 2 (Edit), AI 4 (Polish).
Gate: `trailers/trailer_60s.mp4` = 63.8s, 1920x1080, AAC 160k, -14 LUFS integrated.

Current pipeline (do not reuse as-is):
- `tools/render_trailer.py:571-579` renders silent (`-an`, dummy audio driver), muxes `menu_theme.mp3` whole-length at `volume=0.8` with 2s in / 4s out fades.
- `tools/render_trailer_v2.py:321-342` `mux_1080p_with_music` = blur-pad 1000x700 to 1920x1080 + same fades.
- Game bed: `src/audio/audio.py:1433 _gen_ambient_drone` (55 Hz FM drone, 0.30 amp). Dialogue: `type_tick` chirps + `radio_chatter` garble. No sub, no risers, no ducking.

---

## 1. Music Direction — Replace, Don't Remix

- Genre: Cold War Industrial Darksynth (Carpenter Brut x Mick Gordon DOOM 2016 x Hotline Miami).
- BPM: **100 BPM, D minor**. 100 BPM @30fps = **18 frames/beat exactly**. Cut only on 0.6s grid.
- Tonic: D1 36.7 Hz + D2 73.4 Hz. Distorted saw bass + FM sub. No supersaws, no orchestral hits.
- Deliverable: single `trailer_bed_100bpm_Dm.wav`, 63.8s, 44.1kHz stereo, -20 LUFS pre-master. Replaces `menu_theme.mp3` in trailer mux only (game menu music untouched).

Arrangement (fixed):

| Section | TC | Layers |
|---|---|---|
| Intro | 0:00-0:08 | `ambient_drone` lowpassed 300 Hz mono + `radio_static.wav` at -20 dB + 50 Hz hum at -24 dB |
| Buildup | 0:08-0:28 | Add 8th-note bass D-D-C-Bb, 16th hat, riser_8s (0:08-0:16) + riser_12s (0:16-0:28), snare build last 4 beats. Automate lowpass 300→8000 Hz |
| Silence | 0:28.4-0:28.8 | Full digital silence (12 frames). No fade |
| Drop | 0:29-0:52 | Halftime kick (1 + 3-and), D1 braam every downbeat, distorted bass riff, sniper cracks as percussion |
| Sting | 0:52-1:00 | Down-pitch braam D1→26 Hz over 2s + `rig_low_boom.wav` tail + 1x `alarm.wav` hit. Reverb rings 2s past picture |

## 2. Voice & Radio Comms — Hooks and Filters

Mute `type_tick*` in trailer mix entirely. All dialogue = VO stem with radio treatment.

### 2.1 Lines to record/use (verbatim from `docs/MISSION3_KILL_ORDER.md §6`, `src/missions/m2/sniper.py`, `src/missions/m3/sweep.py`)

- VASILE: "Balaceanu signed the kill order on state radio. Every disciplined team in the building is hunting you."
- VASILE: "Seven seconds — GO! Blue marker — south — MOVE!"
- VASILE: "Nest is dark. Their eyes are out — move while it lasts."
- VOLKOV: "Through that smoke, friend. Shield first — go around his sight."
- VOLKOV: "Window's closing. My engine idles for no one — not even you."
- VOLKOV: "Forty-five seconds. Then I'm a memory."
- VOLKOV: "File's aboard. I drive, you watch the mirrors. DRIVE!"
- BALACEANU (PA, once): "Attention. The terrorist Biribel is inside this facility. Security teams: free fire. My address begins at 22:00 — I will not be interrupted."

### 2.2 Exact ffmpeg filters (trailer VO stem)

```ini
# VASILE — clean VHF van
highpass=f=400,lowpass=f=2800,acompressor=threshold=-18dB:ratio=4:attack=5:release=120,aecho=0.6:0.03:20|0:1

# VOLKOV — close handheld, +proximity bass
highpass=f=350,lowpass=f=2200,bass=g=2:f=150,acrusher=level_in=1:level_out=1:bits=12:mode=log:dc=1,aecho=0.5:0.02:12|0:1,pan=stereo|c0=0.55*c0+0.45*c1|c1=0.45*c0+0.55*c1

# BALACEANU — diegetic PA horn, large hall
highpass=f=600,lowpass=f=3200,acompressor=threshold=-20dB:ratio=6:attack=10:release=300,aecho=0.8:0.35:45|0.6:0.55:35|0:1
```

Squelch (every VO clip): prepend `squelch_head.wav` (30 ms pink burst 480–2350 Hz, -12 dB) + 80 ms gap; append `squelch_tail.wav` (15 ms highpassed click 3500 Hz, -18 dB). Source: cut from `sfx_wav/radio_static.wav`.

### 2.3 In-game equivalent (for later `src/audio/audio.py` patch — DO NOT APPLY YET)

```python
# _radio_voice(buf, kind): kind in ("vasile","volkov","pa")
_bp(buf, 400, 2600) if kind=="vasile" else (_bp(buf, 350, 2200) if kind=="volkov" else _bp(buf, 600, 3200))
_mix(buf, _crackle(len(buf), 0.10, 0.50, 600, 2400), 0.3)
_soft_clip(buf, 2.0 if kind=="volkov" else 1.5)
_multitap(buf, [60] if kind!="pa" else [350, 550], [0.2] if kind!="pa" else [0.45, 0.35], wet=0.2 if kind!="pa" else 0.4)
```

Ducking hook: existing `AudioManager.duck_ambience(frames=90, factor=0.35)` on every `trigger_radio_chatter`. Trailer equivalent: `sidechaincompress=threshold=0.02:ratio=8:attack=5:release=200` on music bus keyed from VO bus.

## 3. SFX Layering — Exact Stacks

Rule: Sub + Transient + Tail. Peak -2 dBTP per hit. All sources in `sfx_wav/`:

| ID | Stack (mix dB) | DSP | Use |
|---|---|---|---|
| BRAAM | `rig_low_boom.wav` 0 dB + `explosion.wav` lp 80 Hz -6 dB + sine D1 36.7 Hz -4 dB, 1.8s exp decay, `soft_clip 1.35` | `lowpass 80`, `env_exp 2.0` | Every act cut: 0:07, 0:17, 0:29, 0:47 |
| RISER_8S / RISER_12S | `_sine_sweep 200→2400 Hz` 0 dB + pink noise lp sweep 300→8000 Hz -4 dB + `empty_click.wav` ticks 8ths→32nds -10 dB | Build with `_sine_sweep` + `_lp` automation | 0:08-0:16, 0:16-0:28. Hard cut to silence |
| SNIPER | `sniper_crack.wav` 0 dB dry + `concrete_impact.wav` -4 dB at +35 ms opp-pan + 170 ms delay wet 0.18 | `_apply_delay(buf,170,0.26,0.18)` | M2 sniper beat 0:25-0:29. Let ring, duck music 0.5s |
| MOLOTOV | `molotov_throw.wav` -4 dB pre + `molotov_explode.wav` 0 dB + `rig_fire_burst.wav` -8 dB tail, crackles hp 3500 Hz | Keep glass FM 3400-5900 Hz untouched | M3 KO montage |
| SUPPRESSED_9MM | `gunshot_distant.wav` 0 dB + `rifle_handle.wav` -8 dB at -5 ms, no reverb | Dry, close | M1 stealth 0:07-0:17 only |
| UNSUPPRESSED | `gunshot.wav` 0 dB + `bullet_impact_enemy.wav` -3 dB + `bullet_snap.wav` -10 dB at +10 ms | `soft_clip 1.45` | Post-drop 0:29+. Must read 2x louder than suppressed |
| BREACH | `breach.wav` 0 dB + `door_rattle.wav` -5 dB + shake 18 | Sync flash frame from AI4 on transient | Stairwell + dock side-door T+20 |

Bed levels under full mix: `room_tone -34.8 dBFS`, `radio_static -38.9 dBFS`, `rain -30.0 dBFS`. Ambience ducks -8 dB under VO.

## 4. Beat-Sync Map — Aligned to `tools/render_trailer.py:459 SECTIONS`

Grid: beat = 0.6s = 18 frames. Cuts on beats only.

| TC | Picture (AI2) | Audio hook |
|---|---|---|
| 0:00-0:03 | Black + title `CALL OF ACARISTAN` | Drone + hum. No drums |
| 0:03-0:07 | Menu (`menu` 3.0s) | First D1 pulse. VASILE whisper bed |
| 0:07-0:17 | M1 warehouse (`m1` 10.0s) | Bass 8ths in. Suppressed clicks on bot bursts. Riser_8s from 0:12. VOLKOV smoke line. BRAAM at 0:07 cut |
| 0:17-0:25 | M2 patrol (`m2` 8.0s) | Hats in. Riser_12s continues. VASILE tanker warning + mini-braam on blast |
| 0:25-0:29 | M2 sniper (`m2sniper` 7.0s) | Strip to riser + `heartbeat.wav` 45 Hz. Laser ticks. BALACEANU PA full line ending at 0:28.4 |
| 0:28.4-0:28.8 | Hard black (12 frames) | SILENCE. No music, no SFX |
| 0:29-0:35 | M3 breakout (`m3break` 7.0s) shiv rush | DROP + BRAAM. `melee_hit` + `breach` on door. VOLKOV window line |
| 0:35-0:41 | Comms relay (`m3comms` 6.0s) | Bass riff. `terminal_glitch` + `alarm` loop low. VASILE archives line |
| 0:41-0:47 | Archives (`m3arch` 6.0s) | Snare build. `pickup.wav` (plate v2) sting on ledger grab |
| 0:47-0:57 | Kill Order (`m3ko` 7.0s) final gunfight | Loudest 10s. Sniper + explosion + auto layered. VOLKOV exfil line at 0:54. BRAAM at 0:47 cut |
| 0:57-1:00 | End card | Down-pitch braam + `mission_complete.wav` chord under. Tail rings past picture |

## 5. Mix Config — Final Mux (replaces `mux_1080p_with_music`)

```bash
# Stems (44.1kHz stereo WAV, all same 63.8s length):
#   bed.wav  = music arrangement §1
#   sfx.wav  = layered hits §3, peaks -2 dBTP
#   vo.wav   = processed dialogue §2, -16 LUFS
ffmpeg -y -i trailer_60s_silent.mp4 -i bed.wav -i sfx.wav -i vo.wav -filter_complex \
"[1:a]volume=0.9,alimiter=limit=0.95[bed]; \
 [2:a]volume=1.0,alimiter=limit=0.95[sfx]; \
 [3:a]volume=1.0[vo]; \
 [bed][vo]sidechaincompress=threshold=0.02:ratio=8:attack=5:release=200[ducked]; \
 [ducked][sfx]amix=inputs=2:normalize=0[mix]; \
 [mix]loudnorm=I=-14:TP=-2:LRA=11,afade=t=in:st=0:d=0.5[a]; \
 [0:v]split[a][b];[a]scale=1920:1080:flags=lanczos,boxblur=18:4,eq=brightness=-0.3:contrast=0.92[bg]; \
 [b]scale=-2:1080:flags=lanczos[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]" \
-map "[v]" -map "[a]" -c:v libx264 -crf 17 -preset medium -c:a aac -b:a 160k -shortest -movflags +faststart trailers/trailer_60s.mp4
```

Targets: integrated -14 LUFS, true-peak -2 dBTP, VO 4 dB above bed when ducked. Silence at 0:28.4 baked into all three stems.

## 6. Future Code Hooks (do not edit yet)

1. `src/audio/audio.py`: add `_radio_voice()` + `_gen_riser()` + `_gen_braam()` using existing `_sine_sweep/_pink/_lp/_soft_clip/_multitap` only.
2. `tools/render_trailer_v2.py:321`: replace `mux_1080p_with_music` with `mux_1080p_trailer_mix` from §5.
3. `src/audio/audio.py: AudioManager.duck_ambience`: wire to `trigger_radio_chatter` for in-game parity.

## 7. Handoffs + Verification

- AI1: land a burst/breach/melee exactly on 0:07, 0:17, 0:29, 0:47. No dead air over drop.
- AI2: cuts on 0.6s grid only. Hold 12 black frames at 0:28.4.
- AI4: flash/shake/chromatic punch on every BRAAM row. No grade crush on silence.
- Verify: `ffprobe` duration 63.8s, `loudnorm` print_format=json confirms -14 LUFS, `python tools/smoke_test.py` → `SMOKE TEST: OK`, `python -m compileall -q src` clean when code patch lands.
