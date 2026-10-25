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

## Multiplayer network test

Run a headless local 4-player match with simulated latency, jitter, and
TCP-loss-recovery stalls:

    python tools/mp_net_soak.py --players 4 --seconds 12 --latency-ms 45 --jitter-ms 12 --loss-percent 1

The match HUD shows client-observed RTT/jitter and snapshot gaps. If an
unexpected disconnect occurs, the game now tries the same invite for up to
20 seconds; press Escape to cancel. The host holds your place briefly and
restores your team, score, position and equipment when the same player returns.
If that saved place has expired, the game warns that the score may reset.
Intentional host exits and kicks are reported without retrying.

Since the current gameplay transport is TCP, the test's loss setting creates
brief stream stalls rather than discarding bytes; it is not a UDP packet-loss
test.

## Development docs

- `AGENTS.md` - working rules: module layout, map authoring, renderer, sprite pipeline
- `docs/engine/STATUS.md` - RPE6 engine status (plan of record)
- `docs/worklog.md` - development history
- `docs/engine/BUGS.md` - known issues and open items
