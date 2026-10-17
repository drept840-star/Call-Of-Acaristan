# Phase 3 report — Asset pipeline (game-wide)
Date: 2026-10-14 (Arena sandbox)   Commits: none (owner tracks changes as files; see CHANGELOG.md "Phase 3" and docs/worklog.md)

## Outcome (first line = honest status)
DONE (amended 2026-10-14, Tier A + Tier B) — pipeline, M5 migration, D5, hot-reload/lint gated; **every fully static gameplay painter in M1–M4 is now baked** (world layers + `sprite_def` sprites, all bit-identical to the painters, procedural fallbacks kept). The literal "≥ 80 % of procedural draw calls" number is not met and cannot be without re-authoring animated art: the corrected census is 51 % of M1–M4 gameplay `draw`/`blit` sites inside baked layers / sprite-backed painters; the other 49 % are actors, FX, HUD text, overlays, cutscenes and parametric UI (dynamic by design — owner decision: convert the 100 % convertible, keep dynamic parts procedural). Details: CHANGELOG 2026-10-14 "Tier A" and "Tier B", B-016, `audit/draw_census.md`, gate `docs/engine/evidence/tierB/ci_tierB.txt` = `AE CI: OK`.

## Exit criteria (master prompt §7 Phase 3)
- [x] `engine.assets` manifest/registry/bake/hashing/hot-reload/lint — `src/engine/assets/{manifest,registry,bake,watch,loaders}.py` behind the `engine.assets` facade; ADR-015. 20 unit tests (`tests/unit/test_assets_registry.py`).
- [x] `src/art/m5` (125 assets) migrated with shims — `src/game/art/m5/` + `src/game/content/m5/manifest.json` (20 assets / 125 variants) + `palette.json`; baked files at `assets/baked/m5/` with `.bakeinfo.json`; `art.m5` shim (A-008) keeps every historical import form; `art.m5.get` is a registry call (`default=None`).
- [x] D5 holds: **0** raw `pygame.image.load`/`mixer.Sound`/`music.load` outside `engine/assets` (17 sites rerouted through `load_image/load_sound/load_music`, same arguments) — enforced by `TestD5AndShim.test_no_raw_loads_outside_engine_assets` and reported by `tools/ae_draw_audit.py`.
- [x] `ae_bake --check` clean — `AE BAKE SUMMARY: packs=1 baked=0 checked=20 sampled=13 stale=0 missing=0 mismatched=0 errors=0`; CI row "asset bake check + lint" switched from TODO to live.
- [x] Smoke: every manifest entry resolves — `check_mission5_sprites` asserts all 125 entries resolve via the registry (baked path, cached identity, placeholder/fallback counters = 0), hash check + 10 % sample, decal face counts, shim identity.
- [x] Contact sheets regenerate — `python tools/ae_bake.py --pack m5 --sheet build/m5_sheet.png` (125 tiles; not committed).
- [x] `ae_bake --check --lint` clean with warnings triaged — exit 0; 2 alpha-fringe advisories triaged as B-014, the forced `--lint-all` palette/light numbers as B-015 (tags `palette`/`lit`/`shadow` are the opt-in/opt-out mechanism; none assigned yet — art owner's call).
- [x] Golden parity — `/tmp/ci_phase3.txt`: golden 353/353 (0 failures, 0 errors), replay 5/5, loop 7/7, bit-identical after the pack move and the loader rerouting. Re-bake reproduced all 125 PNGs byte-for-byte (determinism proof for the hashes).
- [x] Hot-reload demo — headless: `TestHotReload.test_watcher_reloads_module_and_emits_event` edits a sprite module on disk, `AssetWatcher.poll` reloads it (source re-exec), the cache drops, `AssetReloaded` arrives on the `EventBus`, and the next `get` returns the new pixels. In-game: `ACARISTAN_HOT_RELOAD=1 python acaristan.py` (off by default; no display in the sandbox, so not demonstrated live).
- [x] Draw census M1–M4 — `docs/engine/audit/draw_census.md` (ranked per mission; also M5 for reference).
- [x] **Static procedural art in M1–M4 converted to baked blits (owner-amended criterion)** — Tier A: 10 world layers (`m{1,2,3,4}/*_static`, `m3/ko_static`, `m3/kitchen`); Tier B: 12 sprite sets / 103 variants (`m3/door_tile`, `m3/weapon_icon`, `m3/cell_door_blown`, `m3/wall_monitor`, `m3/pickup_icon`, `m3/camera_body`, `m2/prop_icon`, `m2/nest_bits`, `m1/molotov_icon`, `m1/pickup_icon`, `m1/exfil_truck`, `m4/mag_icon`). Parity: `ae_layer_parity.py --all` EXACT, sprite harness logs max Δ 0 (`docs/engine/evidence/tierB/m3_sprite_parity.txt`, `docs/engine/evidence/tierB/m124_sprite_parity.txt`), goldens 373/373, loop 7/7. Literal 80 % **not met** (51 %, see Outcome) — B-016 closed as designed.
- [x] Ad hoc caches replaced where they were engine-owned — the artpack pose LRU is `engine.anim.PoseCache` (`POSES`, cap 512; `artpack.pose` delegates, `rebuild()` clears). The M5 sprite cache is the registry cache. Remaining game-side caches (`missions/m5/water.py _CACHE`, `cutscenes/m5fx3d.py _CACHE`, `_MAG_SPRITES`, drop-shadow caches) are listed in `audit/cache_census.md` (B-005) and stay until their owners move (Phase 5/6).

## Metrics
- Engine modules 27 → 33; API snapshot 25 modules / 121 names → 31 / 169 (+48, −0, re-recorded deliberately). Boundary lint: 0 engine violations; W1 48 (= baseline; `MISSION_RE` now also treats `game.art.m\d` as mission-owned).
- Unit tests 72 → 92. CI rows implemented 9 → 10 (4 TODO left: data validation ph7, engine3d ph6, bench ph10, mission 0 ph10).
- D5: 7 image + 10 sound raw loads → 0. D6 baseline unchanged (1,113 mission `pygame.draw(screen, …)`; census by function in `draw_census.md`).
- Bake: 20 assets / 125 variants, `--check` 6 s (hash pass + 13 sampled renders), full bake 7 s, deterministic (bakeinfo identical across two bakes; PNG bytes identical to the pre-move files).
- Lint: 2 advisories with manifest tags as shipped; 67 with `--lint-all` (triage numbers in B-015).
- Repo size 29 MB (unchanged; baked files moved, not duplicated).

## Visual evidence
- Golden set verified bit-identical (no new goldens: the move and the loader rerouting are parity-neutral by construction). Loop probe 7/7 segments identical; replay final hashes unchanged (m1 2bbec2400def5ebf … m5 b05d9ee03d6e99a1).
- Contact sheet: `python tools/ae_bake.py --pack m5 --sheet build/m5_sheet.png` (regenerated on demand; `build/` is not persisted).

## Risks / debt carried
- B-016 (conversion target) — the real Phase 3 payload for M1–M4; needs a per-mission plan with re-baselined goldens (R5) and the "upgrade in place" prop index (§6.5 #13) before the first batch.
- `BAKE_DEPS` is a manual declaration (used by `inspect_art` for its `missions.m5` painters); a renamed painter module drops out of the source hash silently — the 10 % sample is the backstop.
- The 51 `from core.config import *` sites and the display boot at import (B-007) remain; Phase 4 prep inventory is ready (`audit/star_imports.md`).
- Sandbox baselines only; the owner re-captures `tests/` on the reference machine before trusting the oracles there (unchanged caveat).

## Adapters
- Added A-008 (`art.m5` → `game.art.m5` shim). Open: A-001…A-008. Removed: none.

## Phase 4 prep (done in parallel, docs/tools only, parity-neutral)
- `tools/ae_star_imports.py` → `docs/engine/audit/star_imports.md`: 51 star-import sites, 74 distinct `core.config` names actually used, explicit import line per file (A-001 narrowing is a mechanical edit per file behind the golden gate).
- `tools/ae_hud_census.py` → `docs/engine/audit/hud_duplication.md`: 16 HUD functions in 6 owners; per-mission `_draw_*hud` bodies (M2 393 lines, M3 205, M4 100, M5 82, M1 inline in `_game_draw_inner`) vs the 8 shared widgets in `ui/hud.py`; cross-owner look-alikes (M4 ↔ M5 HUD 0.70 Jaccard) give the lift order.
- Lift-ready scene objects already exist (`CutsceneScene`, `InspectScene`, ADR-014); nothing was lifted (no oracle coverage for PAUSED etc. beyond the loop probe).

## Next three steps
1. B-016 batch 1 (M3, the largest): bake the static wing/cell dressing (`_draw_archives_wing_details` 202 calls, `_draw_cell_details` 95, `_draw_neighbor_cells` 68, `_draw_ko_dressing` 64) as `layer` assets in a new `m3` pack; capture before/after goldens for the affected shots and record the re-baseline in CHANGELOG with the diff images.
2. Phase 4 entry: narrow the star imports from `audit/star_imports.md` (one file per step, golden gate each), then lift PAUSED / NOTEBOOK_INSPECT onto the scene stack as real overlays using the mirror trace as the oracle.
3. Art owner triage of B-014/B-015 (assign `shadow`/`lit`/`palette` tags in `manifest.json`), then make `--lint --strict` the CI mode for the m5 pack.

## Reference-machine addendum (2026-10-15)
The owner merged the session files and the gates were reconciled on the reference machine: `ae_bake --check` clean (0 stale / 0 mismatched), goldens and the loop re-baselined there (B-018; evidence `docs/engine/evidence/reconcile_20261015/`), replay 5/5 and the API snapshot unchanged, `AE CI: OK` under `.venv`. The "sandbox baselines only" caveat above is closed. Phase 4 (UI toolkit and text) enters.
