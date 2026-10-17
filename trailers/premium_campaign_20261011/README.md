# Call of Acaristan — premium campaign short

## Deliverables
- `campaign_final.mp4` — branded main cut, sniper-acquisition hook.
- `campaign_clean.mp4` — same edit without promotional copy or wordmark; authentic in-game text/HUD remains.
- `hook_warehouse.mp4` — alternate immediate warehouse encounter.
- `hook_breach.mp4` — alternate restraint-break cinematic (the filename does NOT describe a playable door-breach mechanic).
- `cover.png` — actual Route 12 gameplay and actual wordmark, 1080 × 1920.
- `*.manifest.json` — source paths, in/out seconds, editorial purpose, composition, copy, audio provenance, per-frame reframe coordinates.
- `*.audio_cues.json` — event-derived sound timecodes.
- `technical_qa.json`, `QA.md`, `capture_report.json`, `vertical_report.json`, `smoke.log` — evidence and limitations.

All cuts: 29.4 seconds, 1080 × 1920, genuine 30 fps, H.264 CRF 20 / medium, yuv420p, stereo AAC 192 kbps / 48 kHz, fast-start. No fabricated frames. No public upload.

## Concept
Selected: Route 12 kill-box. A recognizable sniper-acquisition warning opens inside live combat; a warehouse assignment leads into the state's accusation, restraint-breaking, an existing weapon-retrieval cinematic, archives combat, and a sustained Route 12 fight. Brand/CTA occupy the last 2.6 seconds.

Other concepts tested against assets: the paper trail (objective-led warehouse opening), and state address (broadcast versus prison imagery). Alternate openings are meaningfully different events, not different slogans over one shot.

## Evidence / truthful scope
A — fresh mission gameplay: real M1 warehouse, M2 post-sniper combat checkpoint with acquiring/cover phases, M3 archives checkpoint. Existing input-driver tooling; real movement, weapons, collisions, enemy AI, bullets, impacts, reloads. No HP or ammo refills. Portrait viewport is a capture-process-only display adaptation, not a claim about a supported portrait game release. 60 simulation ticks produce 30 captured frames per second. Save/settings/profile hashes checked where files existed.

B — implemented cinematics: monitor_broadcast, cb_crack, k9_firstperson_grab dispatched through `cutscenes.engine.draw_cutscene_scene`. These are cinematics, not first-person playable combat. The film does not imply otherwise.

C — excluded plans/lore: late campaign M6–M8 events, endings, deaths, betrayals, planned trailer-only 3D shots, unverified release/store/platform claims. Code and runtime capture, not lore alone, support the selected content.

D — old footage: fresh_action clips and legacy masters/shorts inspected via ffprobe and representative frames, then excluded from final. Existing vertical assemblies were blurred-duplicate horizontal layouts. `tiktok_v2/native_source.mp4` is only an old 12-second montage from those tapes, not a new current-build capture.

Rejected capture: `van_handoff.mp4` used a nonexistent dispatch key and yielded a blank scene. It is not used in any export. Fresh landscape captures were exploratory; final gameplay uses portrait takes.

## Sound and rights
No repository MP3, recorded voice performance, TTS narrator, stock music, or third-party sample is used. New original 108 BPM D-minor/adjacent-tone pulse cue is synthesized in `assemble.py`. Game effects are generated directly from `src/audio/audio.py`; sidecars place gunshots, impacts, steps, and reloads at observed simulation events, not a beat grid. A low metal rattle sweetens the actual cinematic restraint rupture. There are no added kills, explosions, enemy spawns, or powers.

No promotional-use license for repository music/voice recordings was located; their existence was not treated as clearance. Ownership of project art, wordmark, bundled fonts, and source-generated effects is assumed from the owner's instruction, not independently legally established. Fonts are referenced from the existing project, not redistributed in the package. Resolve any underlying project-asset ownership issues before public use.

CTA: **Follow for development updates.** No storefront, availability, platform, download URL, or release date is asserted.

## Reproduction
From the existing repository root, with Python, numpy, pygame-ce, Pillow, ffmpeg and ffprobe available:

```powershell
python trailers/premium_campaign_20261011/capture.py
python trailers/premium_campaign_20261011/capture_vertical.py
python trailers/premium_campaign_20261011/assemble.py --revision 2 --one
python trailers/premium_campaign_20261011/finish.py
python trailers/premium_campaign_20261011/verify.py
```

Capture first, render second. `finish.py` uses the main cut's keyframe at 2.000 seconds to retain the exact polished video body for both hook variants; decoded frame hashes validate equality after frame 60. It retains the main uncompressed audio body after 2 seconds and crossfades only within the alternate intro's final 30 ms. AAC encode boundary differences are possible, as with any separately encoded deliverable.

Production game source was not edited. Display/UI adaptation exists only in the isolated capture process. Existing trailers were not overwritten. `review_v1.mp4` is retained in the workspace as first-export evidence, not a final deliverable.

## Post caption
A notebook to recover. A state story to survive. Call of Acaristan — campaign gameplay in development.

#CallOfAcaristan #IndieGame #TopDownShooter #GameDev
