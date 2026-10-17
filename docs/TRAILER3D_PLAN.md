# Call of Acaristan - Cinematic 3D Trailer ("THE CALL")

80 s, 16:9 master (2.39:1 letterbox) + 9:16 cut. Rendered in engine3d (GL),
cast built with `cutscenes.cast3d.humanoid3d()` so everyone is on-model.
Narrated by the game's NARRATOR (same voice as VO_017-VO_024).

Spoiler policy: show M5-M7 setting (martial law, the notebook, Ucilev, the
mansion, the gunship) and hint that Route 12 was "sold". NEVER show: who sold
it, Volkov's fate, Duty vs Revenge outcomes, who dies, Maru's fate.

## Voice-over (record with the TTS, in this order)
Folder: `assets/voice/Trailer/` - name files TR_01.wav ... TR_10.wav, or leave
the TTS names; the trailer tool takes them oldest-first like the game does.

| ID | Line | ~s |
|---|---|---|
| TR_01 | The Kilemeno Ocean. Still a graveyard. | 3.5 |
| TR_02 | Route 12 was supposed to end it. / One ambush. One file. One operator who did what he was told. | 7.5 |
| TR_03 | But files have copies. / And someone in the capital has been reading his. | 5.5 |
| TR_04 | Martial law came on a Tuesday. / The tanks keep the highways open. / The curfew keeps the questions unasked. | 8 |
| TR_05 | A clerk kept a notebook. / Names. Dates. Prices. | 5 |
| TR_06 | Route 12 was never an ambush. / It was a sale. | 4 |
| TR_07 | And the Presidential Guard has a new face. / Same intake. Same training. / Officially, he died two years ago. | 7.5 |
| TR_08 | Everyone in Acaristan answers to someone. | 3 |
| TR_09 | Some orders you follow. / Some you finish. | 4 |
| TR_10 | Call of Acaristan. | 2 |

## Beat sheet (80 s)
| # | Time | Picture | Sound |
|---|---|---|---|
| 1 | 0:00-0:07 | Black -> night ocean, derricks, one flare stack burning. Slow crane down. | Solo duduk/drone, waves. TR_01 at 0:03 |
| 2 | 0:07-0:15 | Route 12 in rain: burnt van, sodium lamp. Biribel walks out of the smoke toward camera. | TR_02 |
| 3 | 0:15-0:21 | Close: a file stamped KRAP on a desk; a gloved hand turns the page. Pull back to Vasile lighting a cigarette (ember glow), face half in shadow. | TR_03 |
| 4 | 0:21-0:30 | Capital at night: tank column, curfew sirens, searchlights on apartment blocks, Guard checkpoint with red armbands. | Drums enter. TR_04 |
| 5 | 0:30-0:36 | Kim Kim border train interior, flickering light: Volkov in his long coat slides a black notebook across the table. Insert: pages of names and numbers. | TR_05 |
| 6 | 0:36-0:40 | Smash to black. Single word on screen: SOLD. | Music cuts. TR_06 in silence |
| 7 | 0:40-0:48 | Guard hangar: gunship rotors spin up. Ucilev walks past the camera, stops, turns his head: the curly mop, the armband. | Rotor thump -> braam. TR_07 |
| 8 | 0:48-1:02 | MONTAGE to the beat (1-2 s shots): M2 sniper ambush, Maru running with the folder, mansion breach, Guards falling in muzzle flash, Biribel reloading, tracers across rooftops, helicopter door-gun POV with Maru flying, missile streak, gunship searchlight finds them. | Full score. TR_08 over the first cut |
| 9 | 1:02-1:10 | Slow-mo: two scopes. Left: the mansion window (silhouette only). Right: a rain-soaked construction site at Route 12 (empty). Biribel's eye in the middle. | Score drops to heartbeat. TR_09 |
| 10 | 1:10-1:16 | Trigger finger tightens -> CUT TO BLACK on the shot. | Gunshot, silence |
| 11 | 1:16-1:20 | Logo: orange road-A reticle slams in, wordmark, "COMING SOON". | Final hit. TR_10 |

## Music brief
80 s, three acts: 0:00-0:36 lonely drone + solo woodwind (duduk/kaval) ->
hard stop at ~0:36 -> 0:40-1:02 hybrid trailer build (braams, taiko, pulsing
strings, ~90-100 BPM) -> 1:02 drop to heartbeat -> 1:16 final impact. A
licence-free track is cut to fit; it doesn't need to be exactly 80 s.

## Build order
1. Storyboard stills (one per beat) for approval.
2. Assets: ocean + derricks, burnt van, tank, train carriage, hangar + gunship,
   mansion facade, Route 12 site, rain/smoke/muzzle-flash/tracer particles.
3. `tools/trailer3d/` - one module per shot (`render(t) -> Surface`), shared
   camera rails, letterbox, grain; render 640x360 -> 1920x1080 nearest.
4. Cut to music + VO, titles in Oswald, export 16:9 + 9:16.

## Build pipeline (as implemented)

Run from the repo root, in order (each step feeds the next):

```
python tools/trailer3d/music_cut.py   # Shell Ghost -> assets/music/trailer_music_80s.wav (+ MARKS)
python tools/trailer3d/vo_mix.py      # + assets/voice/Trailer/*.wav -> trailer_mix_80s.wav + timeline.json
python tools/trailer3d/sfx.py         # + synth sound design -> trailer_final_80s.wav
python tools/trailer3d/render.py      # -> outputs/trailer3d/call_of_acaristan_cinematic_trailer.mp4
```

`render.py --stills` writes one frame per shot to `outputs/trailer3d/stills/`;
`--at 52.9 61.5` renders specific times; `--from 40 --to 50 --out part.mp4`
renders a section. Needs ffmpeg on PATH. Shots live in `shots.py`
(`build_timeline()` maps them to the music marks), props in `props3d.py`,
shared FX/text/grade in `common.py`.
