# M5 shadow finale — recording handoff

The six new performances are not present in First try.zip. The game remains
playable with subtitles plus rain/wind/foley. No synthetic voice is included.
Record clean/dry mono WAV takes; name them exactly as below. The existing voice
loader scans `assets/voice` recursively and explicit VO IDs win. Do not rename
unrelated existing recordings, extend the unnamed-file alignment order, or bake
radio distortion into the takes: the player applies the radio filter.

| File | Actor | Onset | Window | Line |
|---|---|---|---|---|
| VO_192.wav | Ucilev | 9.80 s | 3.90 s | Biribel. Y-3. Same intake. Same training. |
| VO_193.wav | Biribel | 14.10 s | 3.50 s | Then you know why I let Maru go. |
| VO_194.wav | Ucilev | 18.00 s | 4.90 s | I know. You stopped following orders. I didn't. |
| VO_195.wav | Biribel | 23.40 s | 3.00 s | So why am I still standing? |
| VO_196.wav | Ucilev | 27.00 s | 4.10 s | Not tonight. They haven't told me to yet. |
| VO_197.wav | Vasile | 35.40 s | 4.60 s | Biribel, report. ...Never mind. I didn't hear anything. Neither did you. |

Suggested destinations: `assets/voice/Ucilev/`, `assets/voice/Biribel/`, and
`assets/voice/Vasile/`. A 48 kHz / 16-bit WAV is suitable. Keep leading silence
short and fit each window; the current timeline does not stretch around longer
takes. Restart the game after adding recordings (voice files are indexed once).
Remove the corresponding IDs from `KNOWN_MISSING_AUDIO` after takes land, so
future accidental loss is reported by the voice audit rather than treated as
intentional silence.

Ucilev: restrained, precise, almost administrative; "I didn't" is the chilling
contrast, not a villain shout. Biribel: unsettled recognition but no melodrama.
Vasile: starts as a report request, then quietly covers what happened.

The preview renderer exports native ambience/foley and subtitles, not these
recorded performances. Check added takes in the real game, including pause and
skip. Do not interpret the review MP4 as proof that voice recordings exist.
