# QA report — actual checks and limitations

## Completed
- Read AGENTS.md, lore, earlier edit/audio/visual/3D plans, specified capture/assembly references, mission and cinematic implementations.
- Probed repository videos; inspected contact sheets and representative native frames. Rejected old vertical layouts, obsolete release claims, and a blank unsupported cinematic dispatch.
- Executed fresh current-build M1/M2/M3 captures. Real input/AI/collision/weapon paths; no health/ammunition refills. Portrait capture is a process-only viewport adaptation, not production gameplay changes or a supported-platform claim.
- Compared save/settings/profile hashes during capture: unchanged for existing protected files.
- First full export: review_v1.mp4. Inspected 12 sampled export frames, including phone-size gameplay, monitor, restraint break, weapon retrieval, archives, Route 12, and end card.
- Substantive visual revision: restored the complete broadcast bezel/header/accusation; added bounded integer-3x gameplay reframing to enlarge actors without stretching; shortened the weapon-rack insert by 0.5 seconds and added that time to archives contact; shortened Route 12 copy and moved gameplay copy above the combat area. Inspected the replacement export.
- Inspected 12 final export samples, both alternate openings, clean-version samples, cover at 540 × 960, and before/after samples at every main-cut boundary. Text spacing, layout, real-wordmark hierarchy and selected action were reviewed in those images. No blanket glitch/shake/blur-duplicate treatment.
- Kept a 6.8-second continuous Route 12 fight rather than disguising all action with fast montage.
- Both alternate-hook decoded video bodies match main frames 60–881 exactly, checked using ffmpeg framemd5. They share the uncompressed audio body from 2 seconds onward; a 30 ms intro crossfade avoids an abrupt switch. Separate AAC encoding may yield small codec differences.
- All four final files: full audio/video decode via ffmpeg -xerror; 882 video frames; 29.4 seconds; 1080 × 1920; 30/1 constant timestamp cadence; H.264/yuv420p; AAC stereo at 48 kHz; equal audio/video durations; fast-start moov before mdat. No interpolated or fabricated intermediate frames.
- Audio reconstruction uses actual capture event ticks. Mix is centered/mono-compatible; no third-party recordings or narration used. Two-pass normalization was measured again AFTER AAC encoding.
- Initial post-AAC peak measured -0.81 dBTP, above the requested ceiling. Corrected the premaster true-peak target to -2.5 dBTP and remuxed without video generation loss.
- Final measured main/clean: -14.57 LUFS integrated, -1.84 dBTP. Warehouse hook: -14.60 LUFS, -2.86 dBTP. Restraint-break hook: -14.62 LUFS, -3.16 dBTP. See technical_qa.json; use the input_i/input_tp fields, which measure the actual export, not the hypothetical loudnorm output fields.
- python tools/smoke_test.py completed: SMOKE TEST: OK (smoke.log). python -m compileall -q src completed successfully. No game source or renderer changes were made, so renderer-parity checks were not needed.
- Nothing published or uploaded publicly. Existing trailers preserved.

## Limitations / not claimed
- Continuous normal-speed audiovisual watching and subjective listening were NOT available to this agent. I inspected rendered samples and cut-boundary images, not the entire movie playing continuously. No perceptual audio-only audition or phone-speaker listening test is claimed.
- Synchronization follows observed event timestamps and matching stream durations; a human should confirm audible transient alignment and musical taste at normal speed. Full decode and loudness measurements do not prove creative audio quality.
- Muted readability was assessed from sampled pictures, not a continuous muted playback. Opening retention and emotional impact have not been audience-tested.
- Conservative safe areas guided copy and composition. Current live TikTok/Shorts interface versions were not inspected, so actual device overlays should be checked before posting. Authentic HUD elements can fall outside those safe zones; essential promotional copy does not.
- No verified store/release destination was found in project evidence. CTA remains Follow for development updates; no Steam, availability, release-date, platform or download claim.
- No promotional-use licenses for repository music/recorded voices were located; those assets were excluded. New cue is original; effects are generated from project source. Project art/wordmark/font/source ownership has not been independently legally established. Bundled fonts are not redistributed.

## Posting gate
The files are rendered deliverables, not a script or rough-cut-only handoff. They are NOT presented as fully perceptually audio-QA-approved. Before public posting, a human must watch each cut with sound at normal speed on a phone, check current app overlays, and confirm rights to the underlying project art/fonts/effects. Replace any newly identified illegible or broken shot rather than adding camouflage.
