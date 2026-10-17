# M5 finale — The Shadow (integrated build)

## Harbour graphics pass — current art

The user-approved cubic people are retained: body/face meshes and choreography
are identical to the preceding integrated build. The environment is rebuilt
in `cutscenes/m5harbour_art.py`: staggered masonry, proper window bays and
cornices, an extended service passage, gate hardware, paving/drains, roof plant,
bevelled column, restrained wet patches and a designed industrial skyline.

Practical lamp spill is baked into surface colours, with posed-mesh projected
ground shadows and broken world-space river reflections. This is deliberately
stylized lighting, not ray tracing, PBR materials or shadow-map rendering.
Weapon surface colours distinguish steel from dark furniture; grip targets,
body geometry and existing weapon silhouettes are unchanged. The film is
rendered at 1200×572 then filtered to 1000×476, within the original 1000×700 game
screen and subtitle/letterbox layout. Weather motion respects reduced motion.

This is a **graphics pass**, not the planned animation overhaul. The walking,
weapon-holding poses and Maru's stopping/exit timing still require that later
pass. The service passage's geometry now continues beyond the opening; that
must not be confused with Maru's animation already having been extended.

Run `python tools/m5_harbour_art_check.py` to verify the unchanged cubic cast,
unchanged choreography, material/mesh validity, practical spill, reduced-motion
water and repeat-frame/seek-stable lighting.


## What this build replaces

The retired river-gate / scope / reveal / leave / radio / title-card chain is
not active. This replacement uses one fresh 42-second cinematic timeline in
`cutscenes/m5shadow3d.py`, integrated through the existing mission completion
request and cutscene player. Intro and mid-mission art are unchanged. Old
renderer modules remain because the intro shares imports; none of their
ending blocking, camera, poses or shot dictionaries drive this finale.

## Dramatic purpose

Maru escapes because Biribel chooses a person over orders. Ucilev is the
counterfactual Biribel: the same training, same institution, but no break from
obedience. He is a thematic shadow, not a literal clone or supernatural double.
The viewer discovers him with Biribel, not through an earlier omniscient sniper
insert. The later real-identity reveal remains undisclosed.

## Actual staging and timeline

- **0.0–6.2:** a wounded Maru walks through an already-open quay gate. Biribel
  covers the escape; this is no longer a buggy interactive door/stair sequence.
- **6.2–9.6:** hold on Biribel. A small targeting dot and his controlled turn
  establish the danger. No Ucilev insert precedes his discovery.
- **9.6–11.8:** Biribel's across-river view, with a restrained optical push-in.
  Ucilev's first line identifies shared training rather than dumping biography.
- **11.8–13.9:** Ucilev medium, rifle held in a trained stance.
- **13.9–17.7:** matched Biribel medium: Maru was his choice.
- **17.7–23.0:** return to Ucilev. "You stopped following orders. I didn't."
  The uniform, shared stance and repeated framing reinforce the shadow reading.
- **23.0–26.7:** Biribel asks why he is still standing; he does not take a shot.
- **26.7–31.6:** Ucilev says he has not been ordered to kill him. The sniper
  lowers smoothly over 2.7 seconds, with both hands solving to the weapon.
- **31.6–34.9:** Ucilev turns and withdraws behind real roof-column geometry.
  The body and long rifle stay clear of the column. No stair or locked-door exit.
- **34.9–40.0:** return to Biribel; Vasile's radio line makes his knowledge
  unsettling, without a lore explanation or showing Vasile's office again.
- **40.0–42.0:** a quiet reaction hold, then the existing M5 completion screen.

## Dialogue

UCILEV: Biribel. Y-3. Same intake. Same training.

BIRIBEL: Then you know why I let Maru go.

UCILEV: I know. You stopped following orders. I didn't.

BIRIBEL: So why am I still standing?

UCILEV: Not tonight. They haven't told me to yet.

VASILE: Biribel, report. ...Never mind. I didn't hear anything. Neither did you.

Shoulder radios are physically attached, with a live LED for the speaking
operator. The across-river exchange is communication over comms, not shouting.

## Visual and motion implementation

Real engine3d meshes, cameras and canonical character rigs, with a real 3D
software fallback. New near-quay and rooftop sets include an open passage,
mooring points, wet masonry, drains, skyline windows, utility piping, water
ribbons and practical lights. No billboard bloom covers faces or hands.

Compact K9 and long sniper meshes attach to the dominant hand. Fresh two-link
IK solves the support hand at every intermediate lowering frame. Gait distance
is converted to each actor's rig scale, keeping stance feet planted. Reduced
motion disables drizzle and cosmetic camera/body breathing, retaining the
story-critical movement and cameras. Fonts/subtitles are separate from the
3D film area and controls; no double legacy vignette or scanline pass.

## Integration and controls

`missions/m5/finale_script.py` is dependency-free shared timing/script data.
`meta.mission5_ending_shots` contains a single timeline-owned take. The engine
loads the renderer lazily; startup warms sounds, voice lookup and 3D assets
before the visible player clock. Nothing in scene drawing changes campaign
state. The original escort gate still requires both Biribel and Maru.

ESC pauses/resumes the clock and voice. ENTER opens a skip confirmation;
ENTER again completes, ESC cancels and resumes. SPACE cannot bypass the
minimum runtime. Timed cues are one-shot; stale cues after suspension are
consumed rather than played as a backlog. Completion is guarded once, including
confirmed skip. The empty-finale fallback remains available and tested.

## Voice status and remaining production work

The uploaded project contains no takes for these six new lines. This build
ships readable subtitles and native rain/wind/radio/weapon/footstep audio.
It does not invent actor recordings or use synthetic placeholder voices.
VO_192–VO_197 are registered for named takes through the existing radio filter.
See `docs/M5_SHADOW_RECORDING_GUIDE.md`. Existing unnamed voice-file ordering
is deliberately unchanged. Final recorded performances and final GPU playback
on a GL-capable machine are the remaining production checks.

## Validation entry points

`python tools/m5_shadow_check.py`: production playback, pause, skip, save once,
cue timing, deterministic rendering, head-safe cameras, planted feet, solved
weapon contacts, column clearance, reveal order and empty-ending fallback.

`python tools/render_m5_shadow.py --output outputs/M5_Shadow.mp4`: 30 fps review
capture of the actual cutscene state, with native ambience/foley. The review
export does not mix dialogue takes; the game plays them when supplied.

`python tools/smoke_test.py`: full regression suite. See the patch validation
report for the unrelated stale baked tram sprite in the supplied project.
