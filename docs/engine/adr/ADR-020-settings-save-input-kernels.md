# ADR-020: Settings, save snapshots and input as engine kernels; legacy stores as clients

Status: accepted (Phase 9) · Date: 2026-10-16

## Context
- Settings were a flat JSON dict normalised by hand in `core/settings_store`,
  pushed into `core/user_settings.SETTINGS` and assorted `STATE` flags by
  `app.py`. The only accessibility provision was one bool (`reduced_motion`).
- Saves were campaign-progress slots (`core/save_system`) with in-process
  mission checkpoints (M5 phase starters, Maru-fail respawn). There was no
  serialised world snapshot and no determinism proof for one (master D8).
- Input is one raw `pygame.key.get_pressed()` snapshot indexed by `K_*`
  constants at hundreds of sites; no remapping, no gamepad (§6.10).
- Master §6.17/§6.18: versioned snapshots (world + scene stack + mission
  vars + RNG stream states + clock frame), `statehash` for replay checks,
  layered typed settings with live `SettingsChanged`, accessibility as a
  first-class citizen (flash caps, shake scale, text speed, rebinding).

## Decision
1. **Kernels first, stores as clients.** `engine.settings` (typed schema:
   BOOL/INT/FLOAT/STR/ENUM with ranges; layering defaults < file < env
   `ACARISTAN_*` < explicit; strict coercion — an invalid higher-layer
   value falls back to the field default, matching the legacy
   `_normalize` rule; unknown keys preserved and reported; change
   listeners). `core/settings_store` builds its schema from its own
   `_DEFAULTS` and resolves through the kernel: file path, JSON shape,
   env names and public API unchanged.
2. **`engine.save`** validates/serialises `ae.save/1` snapshots
   (`schema/id/frame/mission/vars/world/rng/clock`) and provides
   `statehash`: sha256 over a canonical form with floats quantised to
   1e-4 (sub-quantum noise is benign; real divergence is ≫1 px).
   Capturing/applying is the host's side: `game.save_adapter` (A-013)
   snapshots STATE plain-data fields (instance + class defaults via
   `dir`), the player, per-enemy component dumps + legacy attrs,
   churn-prone STATE object lists (rebuilt wholesale only when every
   attr is plain data), mission-package module globals, and the stdlib +
   `legacy` RNG states. Restore never aliases the snapshot's mutables
   and never materialises class defaults onto instances. Snapshots are
   captured at the four M5 checkpoint starters alongside the legacy
   slot write; the legacy respawn flow stays authoritative.
3. **Determinism proof is a tool, not a baseline.** `tools/ae_replay_check.py`
   runs one replay segment per mission: capture → deliberate mutation →
   restore must reproduce the snapshot bit-for-bit, and capture → 30
   frames → restore → same 30 frames must land on the same
   `ae_replay` oracle hash as the uninterrupted run. (Capture happens
   after a 30-frame warm-up: lazy systems initialise — and draw RNG —
   on the first update; real checkpoints are mid-mission.)
4. **Accessibility is three live settings**, parity-exact at defaults:
   `shake_scale` (int %, at the `core/camera.py` chokepoint — magnitude
   stays an int because it bounds `randint` — and on cutscene handheld
   in `m5fx3d.set_cam`), `flash_reduction` (caps the `_fx.flash` peak,
   the M2 evidence flash, and the M5 breach white-out via a soft
   luminance ceiling; verified by `tools/ae_flash_check.py`: breach max
   luminance 244.5 → ≤198.7 against a 210 cap, defaults untouched) and
   `text_speed` (typewriter interval in M4/M5 flow + the app cutscene
   player). All three are in the settings UI (ACCESS COMFORT rows,
   GAMEPLAY text speed) and mirror live into `SETTINGS`/`STATE`.
5. **`engine.input` action map; remap the snapshot, not the readers.**
   `game.input_adapter` wraps the single `keys` snapshot in
   `app._legacy_frame`: a bound physical key additionally presses its
   action's canonical key, a gamepad folds into the same forced set.
   Defaults are the identity (the wrapper returns the snapshot
   unchanged). Bindings persist in `settings["bindings"]`
   (non-defaults only) and are edited on the CONTROLS tab
   (click badge → press key; `fire` stays on the mouse — its canonical
   is not a key).

## Consequences
- File formats (`settings.json`, `save_data.json`) and the legacy
  stores' public APIs are unchanged; old settings files gain the three
  new keys at their defaults.
- Snapshot restore covers live-state fidelity, not resurrection:
  entities that died since capture are skipped on restore (component
  restore also writes component storage before legacy attrs — view
  setters are not always the inverse of the dump). Mid-run resume stays
  with the legacy checkpoint flow by design.
- Default play is bit-identical (golden 373/373, loop 7/7, replay OK on
  the sandbox oracle sets; nothing re-baselined).
