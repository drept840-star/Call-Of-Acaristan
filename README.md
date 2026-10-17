# Call of Acaristan

Top-down action game by **Retardovici Inc.**, running on the in-house
**RPE6** engine (pygame-ce). Campaign missions (`src/missions/`), a
software/GL 3D renderer for cinematic cutscenes (`src/engine3d/`), a
code-authored sprite pipeline (`tools/sprites/`) and a bitmap-font
radio UI (`src/ui/`) all live in this repo.

## Run

    python acaristan.py

Requires Python 3.13+ and the packages in `pyproject.toml` (`pygame-ce`,
`numpy`, `moderngl`). The renderer silently falls back to software when a
GL context is unavailable; force a backend with
`ACARISTAN_RENDERER=gl|software`. Runtime saves (`save_data.json`,
`settings.json`) are written next to the launcher and are gitignored.

## Verify

    python tools/smoke_test.py     # prints SMOKE TEST: OK
    python -m compileall -q src
    python tools/ae_ci.py          # full engine gate: AE CI: OK

## Development docs

- `AGENTS.md` - working rules: module layout, map authoring, renderer, sprite pipeline
- `docs/engine/STATUS.md` - RPE6 engine status (plan of record)
- `docs/worklog.md` - development history
- `docs/engine/BUGS.md` - known issues and open items
