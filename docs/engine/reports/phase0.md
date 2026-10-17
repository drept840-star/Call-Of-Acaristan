# Phase 0 report — Audit, baseline, hygiene
Date: 2026-10-14 (closeout; audit and first baselines 2026-10-11)   Commits: none (owner tracks changes as files; see CHANGELOG.md and docs/worklog.md)

## Outcome (first line = honest status)
DONE in the Arena sandbox. Caveat: the golden/replay/loop baselines that back this report were captured **here** (Linux, pygame-ce 2.5.8, software 3D, sandbox fonts). They are the oracle for this environment's before/after checks. The owner's Windows baselines (365 shots) are not in the archive and were not touched; do not copy `tests/` from here over them without re-capturing.

## Exit criteria
- [x] AUDIT.md complete, with counts — evidence: `python tools/ae_audit.py` → `AE AUDIT: OK`, `docs/engine/audit/*.md` regenerated 2026-10-14 (295 .py files, eol `lf` 295/295 after normalisation).
- [x] Golden baseline captured and reproducible — evidence: `python tools/ae_golden.py capture` → `captured 353 shots (0 errors) in 18.4s`; `verify` → `verified 353 shots: 0 failures, 0 errors` (byte-identical sha256). 353 vs the owner's 365: the shot lists changed with the finale rebuild (one 3D finale shot replaced the retired m5 ending list); the manifest records every id.
- [x] Replay baseline captured and reproducible — evidence: `python tools/ae_replay.py record` then `check` → `m1..m5: OK 30 snapshots match`, `AE REPLAY: OK` (with the hash-seed pin, B-011).
- [x] Main-loop baseline captured and reproducible — evidence: `python tools/ae_loop.py record` (cold voice cache) then `check` (warm) → `AE LOOP: OK (7/7 segments)` after fixing B-012.
- [x] Line endings normalised in one dedicated change set — evidence: `python tools/ae_normalize.py --mojibake --apply --report docs/engine/reports/phase0_normalisation.txt` → `changed 90 (46 .py)`, every .py proved AST-identical (comments/docstrings only), every other text file proved equal to `CRLF→LF` minus BOM; `.gitattributes` added (`* text=auto eol=lf`, `.bat/.cmd/.ps1` CRLF, binaries marked). Full gate before (`/tmp/ci_m1.txt`) and after (`/tmp/ci_m2.txt`): identical rows, golden 353/353 byte-identical, replay 5/5, loop 7/7, `SMOKE TEST: OK`.
- [x] All tests green — evidence: `python tools/ae_ci.py` → `AE CI: OK (implemented gates)` (8 rows OK, 6 TODO for later phases).
- [x] Docs scaffold — STATUS, AUDIT, BUGS, ADAPTERS, CHANGELOG (new), `adr/ADR-000-template.md`, ADR-001..004, ADR-006, `reports/`.

## Metrics
- Boundary violations: W1 shared → mission 174 (after the owner's finale work) → **169** (= baseline). `audio.m5_finale → missions.m5.finale_script` ×4 removed by moving the module into the mission and adding `AudioManager.register_lazy_generators`; `cutscenes.engine → cutscenes.m5shadow3d` removed by `core.cutscene_registry` (A-003). Engine violations: 0.
- STATE fields: 478 (unchanged; Phase 0 makes no behaviour changes).
- Procedural draw calls (census): unchanged (see `audit/draw_census.md`).
- Duplicated UI functions: unchanged (see `audit/duplication.md`).
- Adapters: added A-003; removed none; open A-001, A-002, A-003.
- Line endings: 74 CRLF + 2 mixed + 1 BOM text files → 0 (5 `.bat/.ps1` kept CRLF by policy). Mojibake (B-003): 242 comment tokens + 5 docstrings → 1 comment + 12 docstring lines left (triple-encoded ASCII art in `missions/m2/draw.py`; `audit/hazards.md#mojibake` lists them).
- Bench: not measured (Phase 10).

## Visual evidence
- Golden comparisons: 353, failures 0, worst: none (byte-identical).
- Images reviewed: finale frames via `tools/m5_shadow_check.py` (`M5 SHADOW FINALE: OK`) after the dispatcher change; no pixel change expected or observed.

## Risks & caveats
- Sandbox baselines ≠ owner baselines (fonts/SDL). Re-capture on the owner machine before relying on them there.
- B-011 (hash-seed dependence) is contained by the harness pin, not fixed. Phase 1 M3 fixes the sources.
- The old patch manifests `PATCH_SHA256.txt` / `MULTIPLAYER_PATCH_SHA256.json` were already partly stale; normalisation changed `tools/build_windows.py`, `src/net/protocol.py`, `src/net/tcp_tunnel.py`, `tools/test_multiplayer_ui.py`, `src/ui/multiplayer_style.py` bytes, so their remaining rows are stale too. They describe historical patches; not regenerated.
- `unittest` tests were rewritten from the engine APIs (39 tests); the owner's original 15 are not in the archive. If both exist later, keep the union.

## Decisions (ADRs)
- No new ADRs. ADR-006 storage decision still with the owner (PNG baselines out of git vs LFS).

## Next phase entry check
- Phase 1 entry held since 2026-10-11 (kernel exists). Remaining Phase 1 exit item: simulation randomness through named streams (B-002) and wall-clock reads through the clock (B-001), with the baselines identical; plus B-011 at the source.
