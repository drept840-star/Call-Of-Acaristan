# FIXES_STORIES — story consistency pass

> **2026-10-20.** A full read of the shipped game text against the story bible
> turned up eight contradictions, two of them visible to a player mid-campaign.
> All eight are fixed here, plus the foreshadowing gaps that made the M6 twist
> arrive as a surprise instead of a payoff.
>
> The rule for every fix below: **the shipped game wins, the bible is corrected
> to match it.** Where a fix needed a line of dialogue, the recorded take is
> protected — no existing voice file was re-cut, and no story beat was deleted.

| # | Contradiction | Severity | Fixed in |
|---|---------------|----------|----------|
| 1 | Balaceanu's vendetta was "six years" but the rumour was one year old | **Player-facing** | lore timeline (kept the takes) |
| 2 | The black notebook had two different sets of contents | **Player-facing** | `ui/hud.py`, `docs/LORE.md` |
| 3 | Three different answers to "who authorised Route 12?" | **Player-facing** | `ui/upload_os.py` |
| 4 | M5 was "a week after the Vostral" (Day 11) *and* Day 8 | Doc vs. code | `missions/m5/`, `MISSION5_PLOT.md` |
| 5 | M4 was "the same night" *and* 48 hours later | Doc vs. code | `MISSION4_PLOT.md` |
| 6 | M8 was Day 13 on the calendar, Day 12 in the dialogue | Doc | `docs/LORE.md` |
| 7 | Retardovici: Balaceanu's puppet, or the puppeteer? | Bible vs. bible | `missions/m4/meta.py`, M3/M4 docs |
| 8 | Two characters claimed the same Y-3 intake; the roster said they were one | Bible vs. code | `core/config.py`, `m6films.py` |
| G1 | The M8 foreshadowing retrofit had never landed (5 of 7 plants) | Gap | M1, M2, M4 |
| G2 | `LORE.md` documented M7/M8 as canon; neither mission exists | Gap | `docs/LORE.md`, M7/M8 plots |

---

## 1. "Six years" against a one-year-old rumour

**Was.** Three shipped lines put the vendetta at six years:

* `missions/m3/meta.py` — *"Balaceanu's six year vendetta against Biribel for the
  Y-1 Vostral leak."* (both halves of that sentence cannot be true)
* `voice_manifest.py` VO_010 (Balaceanu) — *"Six years I have waited to show the
  nation what a KRAP lie looks like."*
* `voice_manifest.py` VO_053 (Biribel) — *"He spent six years trying to kill a
  rumor."*

…while `docs/LORE.md` dated the leak to **Y-1** and Biribel's KRAP service to
**Y-3**. A six-year hunt is impossible in both directions: the rumour is one
year old, and Biribel has been in uniform three years.

**Fixed by moving the rumour, not the line.** The two takes stay exactly as
recorded; the *timeline* was wrong, not the dialogue. The Vostral is now six
years old because **Biribel said it out loud in the ranks at Y-6**, years before
KRAP existed, and it stayed service gossip for five years. At **Y-1** it came
out through KRAP field channels and reached the civilian press — that is the
moment it became a charge Balaceanu could not dodge, because denying it means
producing his classified service record in open court.

So the two numbers now mean different things and both are true:

* **six years** — the age of the *rumour* and of the hunt (VO_010, VO_053), and
  the age of the *lie* itself: the service record was assembled from blank
  forms in 2019, the year Balaceanu became PM.
* **one year** — the age of the vendetta's *operational* phase: every
  "high-risk stabilization assignment" since Y-1 is an attempt on Biribel.

**Touched:** `docs/LORE.md` (Balaceanu entry, Y-6, Y-3, Y-1),
`docs/MISSION3_PLOT.md`, `docs/DOCUMENTARY.md`,
`src/missions/m3/meta.py` (story flag only). **No voice file touched.**

## 2. The black notebook had two contents

**Was.** The M1 evidence panel (`ui/hud.py`) lists the notebook's contents as the
**FuegoTech serial registry** — `FT-7742…7745`, IPA procurement `#8841-8844`,
FuegoTech Ind., Kilemene Sector, with the commander's note *"The fire burns
both ways."* The M6 boxcar reads the same object as *"…Route 12. Movement order.
Authorization — that's Vasile's code."* `LORE.md` and `MISSION6_PLOT.md` both
called it the same book. A player who inspected it in M1 and read it in M6 was
holding two different documents.

A second problem sat underneath: `LORE.md` had Volkov selling the notebook from
**Y-0.5** — six months *before* the Route 12 ambush it supposedly contained the
movement order for.

**Fixed by making the book two-part and the copy damaged.**

* The logbook's bulk is the registry (unchanged in M1).
* Loose at the back is a **leaf**: a Route 12 corridor movement schedule whose
  authorization column is a KRAP relay code. Volkov copied it in during the
  final days before the ambush, because it was the one thing worth selling to
  anyone who could stop it — which is why the Y-0.5 trade is the *registry*, and
  the leaf (and the M1 handoff) is Y-0.
* Biribel's copy is **water-damaged** from the rainy M1 exfil, so the schedule
  and the auth column are illegible to him — which is why the M6 read is a
  reveal and not a callback. Volkov's copy is dry.

**Touched:** `src/ui/hud.py` (one new evidence row: *"1 loose leaf — R12
schedule, water-damaged"*), `docs/LORE.md` (Volkov entry, Y-0.5, M1, M6),
`docs/MISSION6_PLOT.md`.

## 3. Who authorised Route 12?

**Was.** The auth chain the player uploads in M2 (`ui/upload_os.py`,
`auth_chain.log`) read:

```
AUTH NODE 1: RETARDOVICI, S. - PRESIDENTIAL ... AUTHORIZED: DECREE 47 SIGNATURE
AUTH NODE 2: BALACEANU, V. - KRAP LIAISON    ... AUTHORIZED: ROUTE 12 OPERATIONS
AUTH NODE 3: [REDACTED] - MAG FORWARD OPERATIONS (forged)
```

while the M6 reveal says **Retardovici ordered Route 12 and Vasile's codes
carried it out**. Two different answers, and node 2 was also nonsense on its
face: the Prime Minister is not a *KRAP liaison* — that is Vasile's job, and
the "V." initial is Vasile's.

**Fixed by rebuilding the chain as four nodes, in the order the order was
given.** The President signs the cover; the Prime Minister countersigns the
frame (he wanted Biribel dead too); the KRAP liaison signs the convoy movement
order; the MAG node is forged.

```
AUTH NODE 1: RETARDOVICI, S. - PRESIDENTIAL   OMEGA   DECREE 47 SIGNATURE
AUTH NODE 2: BALACEANU, V.  - PRIME MINISTER  DELTA   ROUTE 12 FRAME-UP (COUNTER-SIGNED)
AUTH NODE 3: VASILE, C.     - KRAP LIAISON     GAMMA   ROUTE 12 OPERATIONS (CONVOY MOVEMENT ORDER)
AUTH NODE 4: [REDACTED]     - MAG FORWARD OPS  ????   (forged)
```

The M2 evidence now **corroborates** the M6 reveal instead of fighting it — and
it plants the reveal: the player has had Vasile's name on a Route 12 order
since M2, so *"Route 12 went out on your code"* lands as recognition.

**Touched:** `src/ui/upload_os.py` (chain + the one-line summary in the info
window), `docs/LORE.md` (M2 entry).

## 4. M5 fell after M6 on the calendar

**Was.** `MISSION5_PLOT.md` and `src/missions/m5/__init__.py` both opened with
*"A week after the Vostral"* (the Vostral is Day 4 → M5 = Day 11), while
`LORE.md` put M5 at **Day ~8** and M6 at **Day ~10** — so on the M5 wording,
M6 happened *before* M5. Maru's line *"Balaceanu was breathing too, last week"*
sided with the week.

**Fixed to Day ~8** (four days after the Vostral; M4 ends at dawn Day 7, so
there is a one-day gap), because the Day-8 reading makes the whole chain work:
M6 = Day 10 → Vasile's *"the mansion in two nights"* → M7 = Day 11 dawn →
*"the offer stands. Tomorrow night."* → M8 = Day 12.

**Touched:** `src/missions/m5/__init__.py`, `src/missions/m5/meta.py` (Maru's
line: *"last week"* → *"two days ago"*), `docs/MISSION5_PLOT.md`,
`docs/LORE.md`.

## 5. M4: "the same night" or forty-eight hours later?

**Was.** `MISSION4_PLOT.md` said *"M4 cold open: the same night, the capital."*
The shipped line says the opposite (VO_078: *"Forty-eight hours after the
Vostral…"*), as does the same doc's own shot list and `LORE.md`.

**Fixed:** the doc now says **two days later** (Day 6, ending at dawn Day 7) and
carries a note that the shipped line is the authority.

**Touched:** `docs/MISSION4_PLOT.md`, `docs/LORE.md`.

## 6. M8 was Day 13 in the bible and Day 12 in the dialogue

**Was.** `LORE.md` dated M8 to Day ~13; the shipped offer chain (M6: *"the
mansion in two nights"* → M7: *"tomorrow night."*, with M6 = Day 10 and M7 =
Day 11) puts it on **Day 12**.

**Fixed:** `LORE.md` now says Day 12 and explains the chain.

**Touched:** `docs/LORE.md`.

## 7. Retardovici: puppet or puppeteer?

**Was.** `MISSION3_PLOT.md` called him *"a cape Balaceanu hides behind"*,
`MISSION4_PLOT.md` called him *"the puppet who just ate his own handler"*, and
`missions/m4/meta.py` said *"Retardovici's puppet strings are cut"*. `LORE.md`
and `MISSION5_PLOT.md` said the opposite: he is the real puppeteer, who used
Balaceanu as his attack dog for six years, gave the Route 12 order through
Vasile, and threw Balaceanu away live on air.

**Fixed by labelling the M3/M4 reading as the reading, not the truth.** The M5
reveal is a deliberate re-read of M3/M4, not a bug in them — but the bible
contradicted itself, and `m4/meta.py` still asserted the puppet version as
fact. Both now carry the note: *M3/M4 are written to be re-read; M5 shows the
cape was holding the strings.*

**Touched:** `src/missions/m4/meta.py`, `docs/MISSION3_PLOT.md`,
`docs/MISSION4_PLOT.md`, `docs/LORE.md`.

## 8. Two Y-3 squadmates, one identity

**Was.** `core/config.py` commented the two speaker colours as *"same Y-3
squadmate as OLD SQUADMATE, now the M5 shadow"* — i.e. it claimed the friendly
barracks NPC **is** Ucilev, which cannot be true: Ucilev leads the raid on the
print works while the squadmate stays in the Guard HQ, and the M6 file reads
`INTAKE KRAP 3/7` while the M5 photo pinned by the decree says `KRAP 4 - Y-3
INTAKE`.

**Fixed:** they are two different men from the same **KRAP 4 / Y-3** cohort.
The comment now says so, the M6 personnel file reads `KRAP 4 // Y-3` (matching
the photo the player has been looking at since M5), and the M5 plot doc records
that the OLD SQUADMATE's "Y-3 intake" line is *his* cohort — not Ucilev's
line, which is *"Biribel. Y-3. Same intake. Same training."* (the shipped text
in `missions/m5/finale_script.py`; the older draft line in the doc was never
recorded and is gone).

**Touched:** `src/core/config.py`, `src/cutscenes/m6films.py`,
`docs/MISSION5_PLOT.md`, `docs/LORE.md`.

---

## G1. The M8 foreshadowing retrofit never landed

`MISSION8_PLOT.md` lists seven plants that make the Vasile twist feel planned.
Only two existed. The other five are now in the game:

| Plant | Where it landed |
|-------|----------------|
| Vasile pockets the notebook without reading it: *"Good. I've got it. Later. You need sleep."* | **M1** — the escape cutscene (caption at frame 392, radio VO; VO_198) |
| Vasile's line before the kill-box: *"Route's clean. I checked it myself."* | **M2** — the opening radio line of the 3D kill-box film (VO_199) |
| Half a second of dead air on Vasile's channel before the first round | **M2** — `radio_static` in the gap before the shot lands on Gabi |
| Vasile steers Biribel away from the arrest: *"You don't need to see him. Trust me."* | **M4** — the arrest beat ladder, between the order and the loyalist confusion (VO_200) |
| The M2 auth chain carries Vasile's name on a Route 12 order | **M2** — `ui/upload_os.py` (see item 3) |

The three new lines are registered as **VO_198 / VO_199 / VO_200** in
`audio/voice_manifest.py` and listed in `KNOWN_MISSING_AUDIO`: there is no take
yet, so they play caption-only until someone records them. They were **not**
added to `VOICE_ORDER` — that list drives the automatic matcher for unrenamed
TTS exports, and a new id there would have stolen one of the existing Vasile
clips.

## G2. M7 and M8 do not exist

`LORE.md`'s Appendix A described M7 and M8 in full — two endings, Bodi at the
border, Ucilev's epilogue — as if they were canon. The build stops at M6:
there is no `src/missions/m7/` and no `src/missions/m8/`.

**Fixed by labelling them.** `LORE.md` now carries a status block at the top
(*Missions 1–6 are shipped; 7 and 8 are design*), each M7/M8 entry in the
timeline is marked *Planned — not yet implemented*, and both plot docs open
with the same banner. Nobody should quote those missions as shipped facts.

---

## The canon after this pass

* **The Vostral** — a six-year-old whisper (Y-6, the ranks) that reached the
  press at Y-1. Balaceanu cannot deny it without a trial. He kills Biribel in
  action instead, one "stabilization assignment" at a time.
* **The notebook** — Volkov's logbook: the FuegoTech serial registry plus one
  loose leaf (a Route 12 movement schedule with a KRAP relay code). Biribel's
  copy is water-damaged; Volkov's is dry.
* **Route 12** — Retardovici signed the cover, Balaceanu countersigned the
  frame, **Vasile's** code carried the convoy, and the MAG node is forged.
* **Retardovici** — the puppeteer; M3/M4 are written to be re-read.
* **The calendar** — M1 Day 0 · M2 Day 1 · M3 Day 4 · M4 Day 6 (dawn Day 7) ·
  M5 Day ~8 · M6 Day ~10 · M7 Day ~11 (planned) · M8 Day ~12 (planned).
* **Ucilev** — Bogdan Velicu, the *other* man from the Y-3 / KRAP 4 intake,
  listed KIA at Y-2.

## Files touched

```
src/audio/voice_manifest.py        VO_198-200 registered (no takes yet)
src/core/config.py                 speaker-colour comment
src/cutscenes/m6films.py           Ucilev's intake line
src/missions/m1/draw.py            M1 plant: Vasile pockets the notebook
src/missions/m2/sniper3d.py        M2 plants: Vasile's line + dead air
src/missions/m4/flow.py            M4 plant: steering away from the arrest
src/missions/m4/meta.py            Retardovici retcon note
src/missions/m5/__init__.py        M5 day
src/missions/m5/meta.py            Maru's "two days ago"
src/missions/m3/meta.py            M3 story flag: the six-year hunt
src/ui/hud.py                      M1 notebook evidence panel
src/ui/upload_os.py                M2 auth chain (4 nodes) + info summary
src/app.py                         M1 escape cutscene radio VO
src/game/content/timelines/m4.arrest_beats.timeline.json   M4 plant
docs/LORE.md                       the bible, re-synced
docs/MISSION3_PLOT.md  MISSION4_PLOT.md  MISSION5_PLOT.md
docs/MISSION6_PLOT.md  MISSION7_PLOT.md  MISSION8_PLOT.md
docs/DOCUMENTARY.md
```

## Verification

```
python tools/smoke_test.py     ->  SMOKE TEST: OK
python -m compileall -q src    ->  clean
```

The voice check (`voice_manifest_resolves`) passes with the three new
caption-only lines: they resolve through the matcher and are listed in
`KNOWN_MISSING_AUDIO`, and the Vasile speaker folder still matches
83 of 83 recorded lines with one surplus retake, exactly as before.
