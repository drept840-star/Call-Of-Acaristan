# Phase 4 report — UI toolkit and text
Date: 2026-10-15 (reference machine)   Commits: none (owner tracks files; see CHANGELOG.md "Phase 4")

## Outcome (first line = honest status)
DONE — `engine.ui` (Theme + nine standard widgets) and `engine.text` (`T()`, table, fonts, layout, fit
validation) are in the tree, every mission HUD body that was duplicated now calls the shared widget, and
**every player-facing render literal in `src/` reads the string table** (488 keys, 518 call sites; the three
exceptions are the developer console input echo and the two `PROVOCATEURS` sites inside the frozen m5
inspect-art closure — the string half of the **B-024** owner decision, see Risks below). The whole phase landed
parity-neutral: **no golden was re-baselined** — golden 373/373, loop 7/7, replay 5/5, units 176, m1–m4
bake packs byte-identical after every edit (only `.bakeinfo.json`), `AE CI: OK` 13/13.

## Exit criteria (master prompt §7 Phase 4)
- [x] **Zero duplicated HUD code across missions (census re-run).** `docs/engine/audit/hud_duplication.md`:
  m1 47/47 → **37/40**, m2 38/28 → **32/21**, ui/hud 40/34 → **32/34**; m3 1/4, m4 0/0, m5 3/2 unchanged
  (already widget callers). The 8 shared `ui/hud.py` widgets became `engine.ui.std` widgets and their
  bodies were deleted from the missions; the last cross-owner look-alike (m4 `_draw_m4_hud` ↔ m5
  `_draw_hud`, 0.44) was run down and is *the shared widget call sequence itself*, not duplicated bodies —
  their remaining difference is M4's street arrow + hold clock vs M5's filtered hostiles predicate, plate
  and raid timer. Deliberate mission-side exceptions, with reasons, are listed in `subsystems/ui.md`.
- [x] **Text-fit validation passes for every string in every widget it appears in.** `engine.text` ships the
  fit machinery (`fits`), the CI row "string tables + text fit" checks **21** widget/label slots
  (`tools/ae_text_check.py` `FIT_SLOTS`) and reports 0 problems; widgets whose column is not fixed
  (objective banner, prompt, dialogue box) self-fit inside the widget body (banner wrap, prompt font
  fallback + shrink + viewport clamp, dialogue wrap). Numeric-format placeholders are sampled as ints by
  the tool, so `{s:02d}`-style entries are checked rather than silently skipped.
- [x] **Golden parity (UI-composite cutscene frames included).** 373/373 with 0 failures, 0 errors in every
  gate run of the phase (final: `build/ae_reconcile/str_golden.log`); the loop probe 7/7 × 600 frames and
  replay 5/5 stay bit-identical, which is what makes "the missions call the same widget" provable rather
  than asserted.

## What shipped (Work list)
- **`engine.ui`** (`src/engine/ui/`): `Theme` kernel + `std/`: `objective_banner`, `minimap`, `health_bar`,
  `weapon_panel`, `hostiles`, `dialogue_box`, `bottle_hud`, `crosshair`, `prompt`.
- **`engine.text`** (`src/engine/text/`): `T()` + table loader, `strings`, `fonts` (`load_face`),
  `layout` (`fits`/`measure`/wrap); `src/core/font_coverage.py` for face coverage.
- **Widget mapping of the Work list**: DialogueBox ✓, HudPlate ✓ (the *chrome* is the shared
  `art_cache.get_plate_bg`; the content is per-mission and stays), MagIcons ✓ (per-mission art already
  flows through `weapon_panel`'s `mag_icon` callback — the injection point *is* the dedup), ObjectiveBanner
  ✓, HealthBar ✓, Prompt ✓ (`engine.ui.std.prompt`, M3's body, M5 migrated onto it), Minimap ✓, Hostiles ✓;
  **NameTag** and **StealthIndicator** are single-copy UI (MP arena name plate; M5 visibility chip) — they
  are not duplicated anywhere, so no extraction, recorded in `audit/hud_duplication.md` + `subsystems/ui.md`.
- **Deferred for the record**: `HudPlate`'s content, M1's 12-bullet trapezoid ammo panel, M2's curved mag
  panel and M5's quarter HUD stay mission-side on purpose (knob zoo vs 20-line body); Menu/Toast from the
  earlier queue are not on the master Work list and were not touched.
- **String tables**: `src/game/content/strings/en.json` (488 keys) fed by a one-shot codemod
  (`build/ae_reconcile/migrate_strings.py`, 480 sites + 16 hand-migrated f-strings); every migrated call
  keeps the *identical* rendered text, which is why the goldens never moved. The 2 sites inside the frozen
  m5 inspect-art closure were reverted to literals: migrating them changes a hash the m5 bake manifest
  tracks, so they move with the **B-024** decision.

## Metrics
- Engine modules 33 → 49 (boundary lint); API snapshot 47 → **48 modules / 258 public names** (+1 module
  `engine.ui.std.prompt`, +0 removed; re-recorded deliberately per widget addition).
- Unit tests 122 (phase start) → **176** (widget contracts, shim live views, shipped-string values, plate
  chrome pixel parity, prompt clamp).
- String table 0 → **488 keys**, 0 missing, 0 unused; inventory `docs/engine/audit/text_migration.md`:
  518 `T()` calls, **3** direct render literals (dev console + the 2 frozen-closure sites above).
- Census (see above); W1 shared→mission edges unchanged at the 48 baseline.
- Bake: m1/m2/m3/m4 packs re-baked after every HUD/string edit — all rendered files byte-identical, only
  `.bakeinfo.json` differed (m5 not re-baked: B-024).

## Visual evidence
- Golden 373/373 (unchanged files, so no new images): logs `build/ae_reconcile/str_golden.log`,
  `plate_golden.log`, `ch_*_golden.log`, `bottle_*`, `m1m2_*`; loop logs alongside them.
- Widget proofs: `tests/unit/test_engine_ui.py` (draws every widget headless, crosshair palette, bottle
  strip, prompt clamp), `tests/unit/test_art_cache.py` (plate chrome == legacy inline pixels).
- Evidence index: `docs/engine/evidence/phase4_ui_20261015/README.md` (increments 1–5, gates table).

## Risks / debt carried (honest list)
- **B-024** — the m5 bake pack is stale for 3 artifacts (`inspect_art_0/5`, `tram_wreck_0`) and the pack's
  dep list cannot see it; regenerating moves golden `gp.m5.quarter_mid` (309 px). Committed art restored;
  fresh copies kept in `build/ae_reconcile/baked_m5_fresh{,_2}/`. **Owner decision** (regenerate +
  re-baseline that one shot + add the pack deps, or confirm the art). Until then the **string half of that
  decision** is frozen too: migrating `src/missions/m5/inspect_art_street.py` changes a source hash the m5
  manifest tracks (the `m5/inspect_art` entry covers its declared dep), which trips both the bake gate and
  the smoke row — so its 2 sites stay literals (revert kept in `build/ae_reconcile/strbak/`).
- **B-027** (tooling only) — a full-CI run reported 2 red rows (golden
  `cut.m3.archives_transition_shots.01_m3_archives_ingame_join.t25/t50/t75` + loop `boot`/`m1`) while another
  gate run and a game process shared the machine (rows 2-4× slower, `save_data.json` written inside the run's
  window). The same tree is green standalone and in the final run (`ae_ci_phase4d.log`, 13/13). A red row from
  a loaded machine is suspect, not automatically a tree change; details in `BUGS.md`.
- The ADR-014 **scene lift** (PAUSED / NOTEBOOK_INSPECT as real scene-stack overlays) and the B-007/A-001
  **boot refactor** are *not* Phase 4 Work-list items; they stay as the Phase 5 tail. `ui/hud.py`'s desk
  note / notebook / keypad widgets are consequently still on the legacy draw path.
- The generated string keys are mechanical slugs (`m2.q_switch_weapon_rmb_aim_lmb_fire`). They are stable
  and reviewable, but an i18n workshop pass (Phase 7 dialogue work) may want curated names; keys are cheap
  to rename while the table is small.
- B-014/B-015 (art-owner triage for `--lint --strict`) remain open and advisory.
- B-023 fixed in-phase (`_safe_convert_alpha` guarded `display.get_init()` but not a live surface);
  B-025 records the codemod trap that cost a red cycle (AST offsets are UTF-8 **byte** offsets, and every
  binding of `T` — not just assignments — must force the `_T` alias); B-026 records the other one the smoke
  row caught (`"{02}"` is a positional index — six hand-migrated format strings needed `"{:02}"`; a src scan
  in `tests/unit/test_engine_text.py` now guards the class).

## Adapters
- **A-009** extended: the shim list now covers `bottle_hud` and `crosshair`, the cutscene dialogue box, and
  `src/ui/hud.py` grew `THEME`, `draw_pinned_radio`, `PINNED_RADIO_MAX_VISIBLE`; A-009b (facade live
  views) unchanged. Removed: none (A-001…A-009 all still open as designed).

## Next three steps
1. Owner call on **B-024** (one command + one re-baselined golden, or confirm-as-is).
2. Phase 5 (`engine.world` + std systems) per the master prompt; the scene lift rides along as its tail.
3. Phase 7 dialogue half (now unblocked by the table): give the `cutscene.*`/mission-line keys a curated
   naming pass and wire speaker attribution — the text half is already table-backed.
