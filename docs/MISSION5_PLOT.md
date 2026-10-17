# Mission 5 — "Martial Law"

> *"They cheered him for arresting a liar. Nobody asked what he'd do with the keys."*
> — Maru

---

## Logline

A week after the Vostral, the man the nation cheered shows what he bought with
it. President Retardovici declares emergency rule, dissolves parliament, and
folds what's left of KRAP into a new **Presidential Guard** — with **Captain
Vasile** as its commander. Vasile's first order to Biribel: bring in Maru.
Biribel goes to the MAG safehouse to do it, and instead gets Maru out — straight
through the Guard's raid, led by a calm, unhurried operator the state says died
two years ago: **Ucilev Nadgob Ierdna.**

---

## Where We Pick Up (Recap from M4 Ending)

1. **Balaceanu is in a cell**, arrested live on his own airwaves.
2. **The nation cheered the wrong man** — Retardovici, the puppet who ate his
   handler.
3. **Biribel stayed.** The border was open. He didn't take it.

**M5 cold open: Day ~8.** A state TV bulletin: *"Former Prime Minister Balaceanu
was found dead in his cell this morning. Preliminary findings: suicide."* Cut to
Biribel watching it in the old-town safehouse. Nobody in the room believes it.

---

## Setting

**The capital under emergency rule.** Curfew is now permanent; checkpoints wear
new black-and-red Presidential Guard armbands over old KRAP blue.

- **Guard HQ (the old KRAP depot)** — briefing hub. Biribel walks it as a
  walking-sim section: half his old unit in new armbands, half missing.
- **The Lower Quarter** — night streets between the depot and the safehouse;
  Guard patrols, curfew sirens, a burning tram.
- **The MAG safehouse (an old print works)** — presses, paper stacks, a
  basement tunnel to the river. The raid and escape happen here.

**Time:** one night.

---

## The Spine — The Wrong Man on the Throne

M4 left one open thread: *Retardovici on the throne.* M5 pays it off. The
President didn't save Acaristan from Balaceanu — he **used** Balaceanu as his
attack dog for six years, then threw him away live on air to look like a hero.
Balaceanu's "suicide" is the President tidying up.

M5 also begins the second thread quietly: **Vasile is suddenly very
comfortable in power.** He doesn't say anything wrong. He just never seems
surprised.

---

## Characters & Arcs

### Biribel
Ends M5 having disobeyed a direct order for the first time — not from Vasile
as a rebel commander, but from Vasile as the state. He doesn't know yet that
it's the same man it always was.

### Captain Vasile
Promoted to **Commander of the Presidential Guard**. Warm as ever with
Biribel; tired, joking, protective. He orders Maru's arrest "for Maru's own
safety — they'll be shot otherwise." When Biribel lets Maru go, Vasile covers
for him on the radio. It reads as loyalty. On replay, it reads as a man
keeping his asset in play.

### Maru (MAG)
Hunted again — by the state they just helped save. Maru is the only one who
says the quiet part out loud: Retardovici is worse than Balaceanu, because
people *like* him.

### Ucilev Nadgob Ierdna — *new*
The Guard's lead operator. Calm, polite, frighteningly precise. He leads the
safehouse raid personally. At the climax he has Biribel in his sights — and
lowers the rifle. *"Not tonight. They haven't told me to yet."* He doesn't hate
Biribel. He respects him, which is worse. (Full profile in `LORE.md`.)

### President Retardovici
On every screen, never in the room. Speeches about unity, stability and
"finishing the work the Vostral began."

---

## Mission Phases

| # | Phase | Objective | Beat |
|---|-------|-----------|------|
| 1 | **Bulletin** (cutscene) | — | Balaceanu "suicide" on TV. 3D. |
| 2 | **Guard HQ** (walking sim) | Report to Vasile. | Old squadmates in new armbands. Vasile's office: promotion, the order on Maru. |
| 3 | **Lower Quarter** | Reach the print works before the Guard. | Top-down stealth/combat through checkpoints. Optional: avoid killing Guard (old KRAP faces) — tracked, mentioned in M7. |
| 4 | **The Print Works** | Find Maru; get them to the basement. | The raid hits mid-conversation. Close-quarters fight among the presses. |
| 5 | **The Tunnel** | Escort Maru to the river. | Maru wounded (arm), slow. Guard pursuit behind. |
| 6 | **The Standoff** (cutscene) | — | Ucilev's sights on Biribel at the river gate. He lets him go. 3D. |

**Fail state:** death reloads the latest phase checkpoint. Maru dying in phase
5 also fails.

---

## Intro Cutscene Shot-List

```
scene: m5_tv_bulletin      speaker: ANCHOR     "Former Prime Minister Balaceanu was found dead in his cell this morning. Preliminary findings: suicide."
scene: m5_safehouse_tv     speaker: BIRIBEL    "Suicide. He didn't have the spine for it."
scene: m5_retardovici_tv   speaker: PRESIDENT  "Parliament is suspended until order is restored. The Presidential Guard will finish the work the Vostral began."
scene: title_card          speaker: ""         "MISSION 5\nMARTIAL LAW"
```

## Key Scene — Vasile's Office (in-engine, phase 2)

```
VASILE   "Commander. Me. Can you believe it? They gave me a desk with a flag on it."
VASILE   "Maru's on a list. Not my list - his. If the Guard finds them first, they're shot."
VASILE   "Bring them in quietly and I can keep them breathing. That's all I'm asking."
BIRIBEL  "And if I say no?"
VASILE   "Then somebody else goes. Somebody who doesn't care whether they breathe."
```

## Ending Cutscene Shot-List (3D)

```
scene: m5_river_gate        speaker: ""         (Maru through the gate. Biribel turns - a red dot on his chest.)
scene: m5_ucilev_scope      speaker: UCILEV     "Biribel. Same intake as you, Y-3. You don't remember me. Nobody does - that's the job."
scene: m5_ucilev_reveal     speaker: UCILEV     "Not tonight. They haven't told me to yet."
scene: m5_ucilev_leaves     speaker: ""         (He lowers the rifle and walks away into the rain.)
scene: m5_radio             speaker: VASILE     "Biribel, report. ...Never mind. I didn't hear anything. Neither did you."
scene: title_card           speaker: ""         "MARTIAL LAW"
```

---

## What This Resolves

- Retardovici's true nature: not a puppet who broke free — the puppeteer.
- Balaceanu's end: silenced by the man who used him.
- Biribel's position: officially loyal, secretly protecting MAG.

## What It Leaves Open (For M6)

- Who is Ucilev, and why does the state list him as dead?
- Why is Vasile never surprised?
- Volkov is still out there — and still has a copy of the notebook.

---

## Technical Notes

- **Package:** `src/missions/m5/` following the M4 facade pattern
  (`meta → maps → world → flow → systems → draw`), stage driver
  `STATE.mission5_stage`.
- **Cutscenes in 3D:** bulletin, Vasile's office reveal and the river standoff use
  `engine3d.Renderer(...)` (GPU with software fallback) in the
  `missions/m2/sniper3d.py` film style: one timeline, VO-anchored cuts.
  Characters via `r.add_humanoid(...)`.
- **New rig specs:** Ucilev (messy hair, thick brows, Guard uniform), Maru
  (bandana), Vasile, Guard troopers (black jacket + red armband). See the cast
  sheet in `tools/cast_sheet.py`.
- **New state:** `STATE.m5_guard_kills` (Lower Quarter mercy tracking, read by M8).
- **Verification:** smoke checks for boot, stage transitions, checkpoint routes,
  Maru escort fail, and each 3D shot rendering on both backends.
