# Phase 9 report — save/load, determinism, settings, accessibility (RPE6)

Status: **DONE in the sandbox** (2026-10-16). Kernels for settings,
save/statehash and input are in `src/engine/`; the legacy stores are
their clients; accessibility (shake scale, flash reduction, text speed),
key remapping and gamepad ride on top with parity-exact defaults.
Owner reference-machine `ae_ci.py` re-run pending, as with every phase.

## What changed
- `engine.settings`: typed layered schema (defaults < file < env
  `ACARISTAN_*` < explicit), strict coercion/clamping, unknown-key
  preservation, change listeners. `core/settings_store` resolves through
  it; `ACARISTAN_SHAKE_SCALE=25` demonstrably overrides the file value.
- `engine.save`: `ae.save/1` snapshot validation + canonical
  serialisation; `statehash` (floats quantised to 1e-4).
- `engine.input`: action map (canonical/bound key + pad per action),
  pressed-set remap, gamepad fold-in. Identity by default.
- Settings adoption: new persisted keys `shake_scale` (%), `flash_reduction`,
  `text_speed` (0/1/2 → 0.5×/1×/2×) flow file → `SETTINGS`/`STATE` → live
  consumers: camera shake chokepoint, cutscene handheld + flash peak,
  breach white-out cap, M2 evidence flash, typewriter intervals.
  Settings UI gained COMFORT rows (ACCESS), a Text Speed stepper
  (GAMEPLAY) and a live CONTROLS binding tab.
- `game/save_adapter` (A-013): `ae.save/1` capture/restore against live
  state; snapshots written at the four M5 checkpoint starters next to
  the legacy slot data (respawn flow unchanged and authoritative).
- `game/input_adapter`: per-frame snapshot remap + gamepad merge at the
  one `keys` site in `app._legacy_frame`.
- New tools: `tools/ae_replay_check.py` (D8 proof, CI row),
  `tools/ae_flash_check.py` (breach luminance cap, CI row).

## Evidence (Arena sandbox, 2026-10-16)
- Unit tests: 271 OK (11 in `tests/unit/test_engine_settings_save_input.py`:
  kernels + adapter round-trips).
- Golden 373/373, loop 7/7, replay OK, replay-check OK (5/5 segments,
  mutation-restore and continue-restore-continue proofs), smoke OK.
- AE FLASH: OK — breach max luminance off ≈ [238–245] → on ≤ 198.7 (cap 210).
- AE API: 79 modules / 535 public names (deliberately re-recorded at M1/M2).
- AE TEXT: OK after the CONTROLS tab rewrite. Boundaries OK (82 engine
  modules, W1 48).

## Leftovers / notes
- Snapshot restore is live-state fidelity, not resurrection (dead
  entities are skipped); see ADR-020.
- `_binding_capture` intercepts the next KEYDOWN in the settings state;
  ESC cancels capture, so `skip` cannot be bound to ESC (it already is
  by default).
- No behaviour change at default settings; nothing re-baselined.
