# docs/history — delivery notes from before the engine migration

Moved out of the repository root on 2026-10-14 (RPE6 housekeeping). Nothing here
is read by code, build or tests; it is kept as a record of intent and of how the
overlay patches were delivered.

- `MASTER_PROMPT.md` — the "Big Polish & Fix Pass" agent brief (pre-RPE6).
- `FIXES.md`, `IMPLEMENTED.md` — notes from the Mission 4 fix pass and the graphics rework.
- `MISSION5_W1..W7_README.txt` — Mission 5 wave overlays (what each zip changed).
- `MULTIPLAYER_PATCH_README.txt`, `SETTINGS_PATCH_README.txt`, `PATCH_INSTRUCTIONS.txt`, `TUNNEL_TEST_RESULTS.txt` — multiplayer/tunnel patch notes.
- `PATCH_SHA256.txt`, `MULTIPLAYER_PATCH_SHA256.json`, `manifest.json` — overlay checksum manifests. **Stale**: every text file was re-normalised to LF on 2026-10-14 (`docs/engine/reports/phase0_normalisation.txt`), so these hashes no longer match and must not be used to verify files.

The current plan of record is `docs/engine/STATUS.md`.
