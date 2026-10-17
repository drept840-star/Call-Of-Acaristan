# AUDIT T5 — String & Overlay Origins

**Role:** Terminal 5 (Overlay & String Origin Specialist)
**Mode:** READ-ONLY. No source files were modified.
**Scope:** Origin of the trailer storyboard strings (`laser to helmet-off`, `truck inspection`,
`hand on valve`, `warehouse push`, `glint to muzzle flash`) and the orange debug box.

---

## 1. Executive summary

| Question | Answer |
|---|---|
| Where do the 5 strings live? | **One place only:** `tools/render_trailer_v2.py` → `EDITOR_EDL` (list literal, lines 48–93). Not a dict, not a config, not the game. |
| Are they still on screen? | **No.** In the current working tree the tail half of every caption is *structurally unreachable* on screen. Verified by frame-grabs from the shipped MP4. |
| What draws the orange box? | `bug_tag()` — `tools/render_trailer_v2.py:228-241`. **Still live, 4 call sites.** |
| Is the box at the bottom? | **No — it is at the TOP** (`by = 8`, top-centre) in current code. The *original* bottom box was a different, already-deleted function (see §5). |
| Which render did the user watch? | A build **older than 2026-09-26 23:10:37** (last mtime of `render_trailer_v2.py`). Both MP4s currently on disk post-date that fix. |

**Bottom line:** the bizarre strings are already suppressed. The surviving defect is the
orange-spined `bug_tag()` box, which is a **PLAN_4 §1.1 regression** — it re-introduces exactly the
per-section debug label that PLAN_4 ordered deleted.

---

## 2. Task 1 — Repo-wide grep for the exact strings

Command run (case-insensitive, whole repo, all file types):

```
rg -n -i "laser to helmet-off|truck inspection|hand on valve|warehouse push|glint to muzzle flash" .
```

### Complete result set (only 3 files in the entire repository)

| File | Line | Match | Nature |
|---|---|---|---|
| `tools/render_trailer_v2.py` | 58 | `"NOTEBOOK // glint to muzzle flash"` | **LIVE** — `EDITOR_EDL` element |
| `tools/render_trailer_v2.py` | 63 | `"CHECKPOINT // truck inspection"` | **LIVE** — `EDITOR_EDL` element |
| `tools/render_trailer_v2.py` | 65 | `"KILL-BOX // laser to helmet-off"` | **LIVE** — `EDITOR_EDL` element |
| `tools/render_trailer_v2.py` | 68 | `"TANKER // hand on valve"` | **LIVE** — `EDITOR_EDL` element |
| `tools/render_trailer_v2.py` | 177 | `"""('ACT I — BLACK NOTEBOOK', 'warehouse push') from 'A // B'."""` | **DEAD** — docstring example inside `_split_cap()` |
| `docs/PLAN_2_EDITOR.md` | 25 | "Hand on valve, prompt 0.3s max" | Prose (the EDL spec this code implements) |
| `docs/PLAN_4_VISUALS.md` | 11 | `ACT I — BLACK NOTEBOOK // warehouse push` | Prose — listed as a **deleted** legacy cap |
| `docs/LORE.md` | 85 | "truck inspection" | Prose, unrelated narrative |

**Notable negative result — `"warehouse push"`:** this string is **not live anywhere**. The only
code occurrence is a docstring example at `render_trailer_v2.py:177`. The live EDL entry it
documents was replaced by `render_trailer_v2.py:56` → `"WAREHOUSE // mid-sprint, no approach"`.
The user-visible "warehouse push" therefore came from the *pre-PLAN_4* `SECTIONS` table in
`tools/render_trailer.py`, which no longer exists (§5).

**No game-source hits.** `src/` contains zero occurrences. These are pure editorial/storyboard
metadata, not game text — they belong to the trailer tool, not the engine.

---

## 3. Task 2 — Exact storage location

### 3.1 The container: `EDITOR_EDL`, a plain list of tuples

`tools/render_trailer_v2.py:48-93`. Schema declared at lines 46-47:

```python
# (kind, ...) kinds: black/secs | boot/secs | broadcast/secs |
# card/lines/secs/tag | game/tour_key/starter_name/secs/cap_text
```

The strings are the **5th element (`cap_text`) of every `"game"` tuple**. Not a dict — positional.

### 3.2 The complete inventory of live `cap_text` values

| EDL line | `kind` | Section | `cap_text` literal |
|---|---|---|---|
| 54 | game | S04 sniper tease | `ROUTE 12 // 48 HOURS EARLIER` |
| 56 | game | S05 warehouse infil | `WAREHOUSE // mid-sprint, no approach` |
| **58** | game | S06 notebook grab | **`NOTEBOOK // glint to muzzle flash`** |
| 60 | game | S07 Volkov runs | `HANDOFF // Volkov escapes` |
| **63** | game | S09 checkpoint | **`CHECKPOINT // truck inspection`** |
| **65** | game | S10 kill-box | **`KILL-BOX // laser to helmet-off`** |
| **68** | game | S12 tanker valve | **`TANKER // hand on valve`** |
| 70 | game | S13 tanker run | `TANKER RUN // 0:03 countdown sprint` |
| 72 | game | S14 IPA reveal | `CONTACT // flash to casing only` |
| 75 | game | S16 blast | `BLAST // white-orange flash` |
| 78 | game | S18 breakout | `BREAKOUT // shiv to sidearm` |
| 80 | game | S19 heist | `ARCHIVES // Vostral beacon` |
| 82 | game | S20 kill order | `KILL ORDER // stairwell breach` |
| 84 | game | S21 dock holdout | `HOLDOUT // door cycles, van covers` |
| 86 | game | S22 uplink race | `UPLINK // SURVIVE THE VOSTRAL` |

Wire format is `HEAD // tail` — a storyboard slug, a `//`, then an internal shot note.

### 3.3 The two consumers, and why the tail can no longer render

**Consumer 1 — `_split_cap()` (`render_trailer_v2.py:176-181`):**
```python
def _split_cap(cap_text):
    """('ACT I — BLACK NOTEBOOK', 'warehouse push') from 'A // B'."""
    if cap_text and "//" in cap_text:
        pre, post = cap_text.split("//", 1)
        return pre.strip(), post.strip()
    return "", (cap_text or "")
```
Splits on the **first** `"//"` only.

**Consumer 2 — `bug_tag()` (`render_trailer_v2.py:228-241`):**
```python
def bug_tag(cap_text):
    act, _ = _split_cap(cap_text)     # <-- tail bound to `_` and DISCARDED
    ...
    t = FONT_BUG.render(act, True, (255, 150, 60))
```
The tail is bound to `_` and never rendered. So `laser to helmet-off`, `truck inspection`,
`hand on valve`, `glint to muzzle flash` are **unreachable pixels** in the current tree.

**Consumer 3 — `caption()` (`render_trailer_v2.py:220-225`):** body is a bare `return`.
Zero draw calls. Furthermore it is **never invoked** (grep: definition at 220, zero call sites)
and `rt.caption` is **deliberately not installed** (see the install block, §3.4). It is
vestigial dead code retained only as a tombstone.

### 3.4 The monkeypatch install block — and what is conspicuously absent

`render_trailer_v2.py:530-539`:
```python
rt.card            = card
rt.make_router     = make_router
rt.run_gameplay    = run_gameplay
rt.run_menu        = run_menu
rt.run_walk        = run_walk
rt.mux_1080p_with_music  = mux_1080p_with_music
rt.mux_1080p_trailer_mix = mux_1080p_trailer_mix
# NOTE: rt.caption is intentionally NOT installed — bottom storyboard pill
# removed, bottom of screen stays clean.
```
`rt.caption` is absent by design (comment at 531-532). The vestigial `_orig_caption =
getattr(rt, "caption", None)` at line 144 resolves to `None` because `render_trailer.py` has no
`caption` symbol at all (verified) — it is a dead defensive guard.

---

## 4. Task 3 — The orange box draw call, and how to suppress it

### 4.1 The exact draw call

**`tools/render_trailer_v2.py:228-241` — `bug_tag()`.** Full body:

```python
def bug_tag(cap_text):
    act, _ = _split_cap(cap_text)
    if not act:
        return
    t = FONT_BUG.render(act, True, (255, 150, 60))   # orange text
    pad_x, pad_y = 10, 5
    bw, bh = t.get_width() + pad_x * 2 + 8, t.get_height() + pad_y * 2
    bx = W // 2 - bw // 2
    by = 8                                            # <-- TOP of screen, not bottom
    bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
    bg.fill((4, 5, 6, 190))                           # dark panel, 75% alpha
    config.screen.blit(bg, (bx, by))
    pygame.draw.rect(config.screen, (255, 120, 0), (bx, by, 3, bh))  # <-- ORANGE 3px SPINE
    config.screen.blit(t, (bx + pad_x + 8, by + pad_y))
```

This is a **direct `pygame` blit onto `config.screen`, outside the game's draw stack** — it is
pasted after `rt.gc.game_draw(cam[0], cam[1])` on every single frame, so no engine flag, setting,
or `show_*` toggle can suppress it. It must be killed at the Python level.

Style constants: `FONT_BUG = IBMPlexMono-SemiBold.ttf @ 16` (`render_trailer_v2.py:32`).

### 4.2 Why it cannot be suppressed by configuration

The box is drawn in the trailer tool, not the engine. Contrast with the engine HUD, which *is*
gated (`SETTINGS.show_crosshair` per `docs/PLAN_4_VISUALS.md:24`; minimap per `PLAN_4 §1.3`).
There is no `show_bug_tag` / `show_caption` knob anywhere — `rg` over the repo returns nothing.
**The only lever is the code path itself.**

### 4.3 All 4 call sites (unconditional, per-frame)

| Line | Enclosing function | Reached by |
|---|---|---|
| **306** | `_run_melee_rush()` | M3 breakout take (routed from `run_gameplay` when `_LAST_KEY == "m3break"`) |
| **352** | `run_gameplay()` | every non-breakout gameplay take |
| **369** | `run_menu()` | menu capture (currently unreachable — `SECTIONS` has no `menu` entry) |
| **388** | `run_walk()` | walking-sim take (currently unreachable — no `walk` entry in `SECTIONS`) |

Effective live sites: **306, 352**. `run_menu`/`run_walk` are vestigial per PLAN_4 §1.2.

### 4.4 Recommended permanent suppression (do not apply — READ-ONLY audit)

**Option A — one-line kill switch (recommended, lowest risk, PLAN_4-faithful).**
Add `return` as the first statement of `bug_tag()`, mirroring the existing `caption()` tombstone
at line 220. Neutralises all 4 call sites at once, no signature churn, no import churn. Keep the
`cap_text` plumbing intact so `EDITOR_EDL` stays self-documenting as an editorial artifact.

**Option B — full excision (cleanest, larger diff).** Delete `bug_tag()` (228-241), all 4 call
sites, `_split_cap()` (176-181) and `FONT_BUG` (line 32), then drop `cap_text` from the
`EDITOR_EDL` `"game"` tuples and the `editor_main` destructure at line 581. Correct if the
storyboard metadata is no longer wanted in the repo — but it destroys the EDL's editorial
self-documentation, so prefer Option A unless AI-2 wants the notes gone.

**Option C — DO NOT DO: strip the `" // tail"` suffixes from `EDITOR_EDL`.** This is cosmetic
only. It shrinks the strings but leaves the orange box and the `HEAD` slug (`KILL-BOX`, `TANKER`,
`CHECKPOINT`, …) rendering. **This is almost certainly the wrong partial fix** and would look like
a fix while the box persists.

### 4.5 Verification gate after any fix

```powershell
$env:ACARISTAN_EDITOR_CUT=1; python tools\render_trailer_v2.py --smoke
python tools\smoke_test.py          # must print SMOKE TEST: OK
python -m compileall -q src
```
Then frame-grab a gameplay frame and confirm zero boxes:
```powershell
ffmpeg -v error -y -ss 20 -i trailers\trailer_60s_silent.mp4 -frames:v 1 check.png
```

---

## 5. Provenance — the original *bottom* orange box (already deleted)

The user described the box as being at the **bottom**. In current code it is at the **top**
(`by = 8`). The bottom variant was a different function, removed earlier:

`docs/PLAN_4_VISUALS.md:9-12` documents it precisely:
> File: `tools/render_trailer.py:127-134` (`caption()`) … Delete `caption()` function.
> Delete per-section `cap` strings: `ACT I — BLACK NOTEBOOK // warehouse push`, …
> Result: **zero bottom-bar (green mono + orange 3px spine on `H-30`)** in any frame.

So the original artifact was: green monospace text + **orange 3px spine**, anchored at
`y = H - 30` (bottom), sourced from a 5-tuple `SECTIONS` table. That is where
**`warehouse push`** lived — it was a `SECTIONS` cap string, not an `EDITOR_EDL` one.

**Verified as applied** to `tools/render_trailer.py`:
- no `def caption` — grep returns nothing (`render_trailer.py` has no such symbol)
- `SECTIONS` (line 545) is now a list of **4-tuples** `(key, starter, secs, mode)` — the `cap`
  element is gone
- `run_gameplay(seconds, router, fight=True)` (line 447) and `run_walk(seconds, router)`
  (line 473) no longer take a `cap_text` parameter
- module docstring line 3: `PLAN_4_VISUALS implementation: zero debug labels, no menu capture.`

`git` history is **unavailable** for this: the repo has a single commit (`310c385 SC COA 20.07`,
276 tracked files) and the entire `tools/` directory is **untracked** (`git status` → `?? tools/`).
`git show HEAD:tools/render_trailer.py` fails. The original `caption()` body can only be
reconstructed from `PLAN_4_VISUALS.md §1.1`, which is what §5 above relies on.

**Therefore: `bug_tag()` in v2 is an unlabelled re-introduction of the exact widget PLAN_4 §1.1
banned** — same design language (orange 3px spine + dark mono panel + per-section storyboard
slug), re-anchored to the top, in a file written after PLAN_4 landed.

---

## 6. Empirical verification against the shipped MP4s

Timestamps (mtime):

| File | mtime | Duration | Which path rendered it |
|---|---|---|---|
| `tools/render_trailer_v2.py` | **2026-09-26 23:10:37** | — | (source of truth) |
| `trailers/trailer_60s_silent.mp4` | 2026-09-26 23:20:34 | **58.000 s** | editor cut |
| `trailers/trailer_60s.mp4` | 2026-09-26 23:21:13 | **58.000 s** | editor cut, 1080p muxed |
| `trailers/trailer_smoke.mp4` | 2026-09-26 23:00:51 | 10.000 s | `rt.main()` |

`58.000 s` matches `EDITOR_RUNTIME = 58.0` (`render_trailer_v2.py:45`) exactly, and is asserted at
runtime by lines 622-623. That positively identifies both `trailer_60s*.mp4` as
**`ACARISTAN_EDITOR_CUT=1` output**, i.e. rendered by the current file — 10 minutes *after* its
last edit.

### 6.1 Frame-grabs — `trailer_60s.mp4` @ t=20 s (inside S10 "KILL-BOX")

Observed on screen:
- **top-centre:** `KILL-BOX` in orange `(255,150,60)` inside a dark panel with a **3px orange
  left spine** → `bug_tag()` confirmed as the live draw call, at the **top**
- **bottom:** clean. No `laser to helmet-off`. No green/orange bottom bar.
- engine HUD still visible (not in scope for T5, listed in §7)

Same result at t=17 s (`CHECKPOINT`) and t=24 s (`TANKER`) from the silent tape.

### 6.2 Frame-grabs — `trailer_smoke.mp4` (older build)

Bottom-strip crops at t=4.0 s and t=6.7 s show **no bottom pill and no spine**. The pre-23:10 build
already had `caption()` neutered.

### 6.3 Conclusion from the frames

**No MP4 currently on disk contains `laser to helmet-off`, `truck inspection`, `hand on valve`,
`glint to muzzle flash`, or `warehouse push`.** The user's video is a build older than
2026-09-26 23:10:37 that has since been overwritten, or was reviewed outside this working tree.
Re-rendering with the current file reproduces the strings' absence.

---

## 7. Collateral findings (adjacent, flagged not fixed)

1. **`bug_tag()` is a PLAN_4 §1.1 violation** — see §5. PLAN_4 requires "zero debug labels" and
   rejects any take containing storyboard slugs. The `HEAD` slugs (`KILL-BOX`, `TANKER`,
   `CHECKPOINT`, `ARCHIVES`, `KILL ORDER`, …) are internal editorial shorthand with no diegetic
   justification. This is the one defect that *is* still reproducible.

2. **Signature incompatibility breaks the default (non-editor) render path.** v2 rebinds
   `rt.run_gameplay` / `rt.run_walk` to 3- and 4-parameter versions
   (`render_trailer_v2.py:315`, `:376`), but `render_trailer.py`'s own `main()` still calls the
   PLAN_4 2-parameter forms at `render_trailer.py:661` (`run_walk(sec_seconds(secs), make_router(key))`)
   and `:673` (`run_gameplay(sec_seconds(secs), make_router(key), fight=True)`).
   With `ACARISTAN_EDITOR_CUT` **unset**, `__main__` dispatches to `rt.main()`
   (`render_trailer_v2.py:626`) and **every** section raises `TypeError: missing required
   positional argument 'router'`. The broad `except` at `render_trailer.py:675-678` swallows it,
   prints `!! section <key> failed`, and the render "succeeds" with **zero gameplay** — a silent
   no-op that still prints `saved ...` and burns a full render. Guard the env flag or make the
   v2 wrappers accept the 2-arg form.

3. **Dead code to remove while in the file:** `caption()` (220-225, never called),
   `_orig_caption` (144, always `None`), `run_menu()` (363-373) and its `SECTIONS` counterpart
   already deleted by PLAN_4 §1.2, `bug_tag()`'s `run_walk` site (388) unreachable since
   `SECTIONS` dropped its `walk` entry.

4. **Engine HUD is still fully on** in every take — `HOSTILES: 0`, `OBJECTIVE: … (0/4)`,
   the `VASILE:` subtitle bar, `BROKEN RADIO [E]` prompt tags, minimap, weapon/H P panels.
   `PLAN_4 §1.3` explicitly rejects takes containing `[E]` / `(0/3)` / `WASD` objective panels
   and >1-line pinned radio. Frames 3 and 5 above show exactly those violations
   (`Inspect staged evidence markers with [E] (0/4)`, `BROKEN RADIO [E]`). Outside T5's string
   mandate but it is the same class of defect and the same PLAN_4 clause.

5. **`rt.mux_1080p_trailer_mix` is installed but nothing calls it** in v2 (`editor_main` only
   calls `mux_1080p_with_music` at line 616). AI-3's 3-stem mix is therefore not wired into the
   editor cut — the shipped `trailer_60s.mp4` carries only the single `menu_theme.mp3` bed.
   Intentional or not, worth confirming with AI-3.

---

## 8. File/line index

| Artifact | Location |
|---|---|
| All 5 strings (live) | `tools/render_trailer_v2.py:48-93` (`EDITOR_EDL`), elements at 58, 63, 65, 68 |
| `warehouse push` (dead docstring) | `tools/render_trailer_v2.py:177` |
| Caption format spec | `tools/render_trailer_v2.py:46-47` |
| **String splitter** | `tools/render_trailer_v2.py:176-181` (`_split_cap`) |
| **Orange box draw call** | `tools/render_trailer_v2.py:228-241` (`bug_tag`) — spine at `:240` |
| Box call sites | `tools/render_trailer_v2.py:306, 352, 369, 388` |
| Box font | `tools/render_trailer_v2.py:32` (`FONT_BUG`, Plex Mono SemiBold 16) |
| Caption no-op tombstone | `tools/render_trailer_v2.py:220-225` |
| `rt.caption` non-install note | `tools/render_trailer_v2.py:531-532` |
| Monkeypatch install block | `tools/render_trailer_v2.py:530-539` |
| `cap_text` destructure | `tools/render_trailer_v2.py:581` |
| EDL runtime assertion | `tools/render_trailer_v2.py:622-623` |
| Env-flag dispatch | `tools/render_trailer_v2.py:620-626` |
| Original bottom box (deleted) | `tools/render_trailer.py:127-134` per `docs/PLAN_4_VISUALS.md:9` |
| Legacy `cap` strings (deleted) | `docs/PLAN_4_VISUALS.md:11` |
| PLAN_4 "zero bottom-bar" clause | `docs/PLAN_4_VISUALS.md:12` |
| EDL source spec | `docs/PLAN_2_EDITOR.md:15-25` |
| PLAN_4 trailer-only scope | `docs/PLAN_4_VISUALS.md:3` |
| "zero debug labels" docstring | `tools/render_trailer.py:3` |

---

## 9. Answers to the three assigned tasks

1. **Where are the strings?** `tools/render_trailer_v2.py` → `EDITOR_EDL` list literal, as the 5th
   positional element (`cap_text`) of `"game"` tuples, in `"HEAD // tail"` format. Exact lines
   58, 63, 65, 68; `warehouse push` survives only as a docstring example at line 177.
2. **Which file/dict/array?** One file (`tools/render_trailer_v2.py`), one array (`EDITOR_EDL`).
   No dict, no config file, no game source. Every repo-wide hit is enumerated in §2.
3. **Which draw call, and how to suppress permanently?** `bug_tag()` at
   `tools/render_trailer_v2.py:228-241` — a raw `pygame` blit onto `config.screen` with a 3px
   orange spine (`pygame.draw.rect(..., (255,120,0), (bx, by, 3, bh))`, line 240), invoked
   unconditionally at 4 sites. It is outside the engine draw stack, so no engine setting can
   disable it. Suppress by making `bug_tag()` a no-op (`return` on entry, mirroring `caption()`
   at line 220) — or excise the function, its 4 call sites, `_split_cap()` and `FONT_BUG`
   entirely. Do **not** merely edit the string literals; that leaves the box on screen.
