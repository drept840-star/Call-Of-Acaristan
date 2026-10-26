# KRAPNET Launcher & Auto-Updater

The pre-game launcher (`python launcher.py`, or `--launcher` on `acaristan.py`)
checks a remote feed for a newer build and can patch the install in place —
no browser download, no re-running an installer. Player saves are never touched.

## Files

| File | Owner | Purpose |
|---|---|---|
| `launcher.py` | CLI entry | `--check-only` (headless status), `--demo-update` (simulated v+1 notice), `--no-launch` |
| `src/launcher/updater.py` | feed + patcher | trust policy, integrity, protected paths, journal/rollback |
| `src/launcher/window.py` | UI | 860x520 logical canvas, presented scaled/letterboxed to any window size |
| `version.json` | local truth | installed version/build, written only after a verified update |
| `launcher_config.json` | config | feed URL, gating, protection, trust overrides |

## Publishing an update

```
python tools/publish_update.py --version 0.2.0 --build 4510 \
    --headline "Patch 0.2.0" --note "Fixed M6 train" --note "UDP polish" --copy-files
```

Writes `dist/update/` containing `version.json` + `manifest.json` + `RPE6-<ver>.zip`
(+ loose per-file deltas with `--copy-files`). Upload that folder to any static
host (GitHub Releases, R2, itch.io). The published `version.json` carries
`manifest_sha256` — the digest of the exact `manifest.json` bytes — so the
launcher can reject a manifest that was tampered with in transit.

## Configuring the feed

In `launcher_config.json` set exactly one:

```json
{ "update_url": "https://example.com/acaristan/version.json" }
```

or point at a GitHub repo's latest release (assets `version.json`,
`manifest.json`, `RPE6-<ver>.zip`):

```json
{ "github_repo": "you/call-of-acaristan" }
```

Until either is set the launcher reports `unconfigured` and shows the local
build card — correct for a dev checkout, and the `--check-only` exit says
`[UNCONFIGURED]` so a shipped build with a missing feed is obvious.

### Keys

| Key | Default | Meaning |
|---|---|---|
| `check_on_startup` | `true` | Poll the feed when the window opens |
| `gate_play_on_update` | `true` | PLAY applies a pending patch first, then launches — a running `.exe`/`.dll`/`.pyd` cannot be replaced |
| `timeout_seconds` | `4.0` | HTTP timeout (x3 for downloads) |
| `allow_downgrade` | `false` | Accept a feed that is older than the installed build |
| `allow_insecure_hosts` | `[]` | Hosts permitted over plain HTTP (loopback is always allowed for `--demo-update`) |
| `protect` | `[]` | Glob patterns never patched, e.g. `["src/missions/m6/**"]` |
| `preserve_files` | saves etc. | Always skipped by the patcher |

## Protected files

A developer's or player's local hotfix is never silently clobbered:

- `launcher_config.json` `"protect"` list (glob patterns, `**` supported)
- `.aca_skip` — one path/glob per line, `#` comments
- `.aca_skip.json` — `{"protect": ["src/foo.py", ...]}`
- Built-in: `save_data*.json`, `settings.json`, `profiles.json`,
  `launcher_config.json`

The notice card reports counts (`KEEPING n PROTECTED FILE(S)`, and an amber
warning for locally modified files that *will* be replaced — a file counts as
locally modified when its mtime is newer than `version.json` and it has a
text-ish suffix).

## Distributing via itch.io

itch is a game store, not a static file host — its download URLs go through
the site's download flow, so the in-launcher updater **cannot** pull a feed
from `user.itch.io` itself. itch's own tooling already covers the whole loop:

```
python tools/build_windows.py
python tools/itch_push.py myuser/call-of-acaristan:windows
```

`tools/itch_push.py` wraps butler (the official itch CLI): it pushes the
`dist/Call of Acaristan` onedir to a channel and fails loudly on the common
mistakes. One-time setup: install butler from <https://itch.io/docs/butler/>,
put it on PATH, run `butler login`.

- **Players on the itch app get updates automatically.** A new push to the
  same channel is offered (and by default applied) by the app, using butler's
  delta patches. That is the itch-native "I upload a new build, the player
  receives it".
- **Channel names are load-bearing.** Keep `windows` stable; the app updates
  a channel in place, and a renamed channel strands installed players.
- **Saves survive app updates.** `save_data.json` and friends are runtime
  files that no pushed build contains, and butler patches only touch files
  the build knows about (which is why `butler clean` exists for manual
  pruning). Verify once with a real push before relying on it at scale.
- **Browser-download players get no auto-update from itch** — they re-download
  from the page.

### What the launcher does on an itch install

The itch app drops `.itch/receipt.json` in the install folder; the launcher
detects it (`itch_receipt_path`) and, with no feed configured, the status card
reads **ITCH.IO INSTALL // UPDATES ARRIVE VIA THE ITCH APP** with a matching
tip line, instead of advertising a relay check it cannot fulfill.

### Hybrid: in-launcher patching for browser-download players

If you also want players who grabbed a zip from the browser to get in-place
patches, host the three-file feed (`version.json`, `manifest.json`,
`RPE6-<ver>.zip` from `tools/publish_update.py`) on any static HTTPS host —
GitHub Releases is free and natively supported via `github_repo` — and set
`update_url`/`github_repo` in the shipped `launcher_config.json`. The same
launcher then patches in place, gated PLAY first. itch app players are
unaffected either way: unconfigured + receipt means the launcher simply steps
aside.

## Trust model

- Every fetched URL must be **HTTPS**. Plain HTTP is refused unless the host is
  loopback (demo feed) or listed in `allow_insecure_hosts`. `InsecureTransport`
  shows as `FEED REFUSED // UNTRUSTED UPDATE SOURCE`.
- `manifest_sha256` in the feed must match the delivered manifest bytes
  (`IntegrityError` → `refused`).
- `zip_sha256` and per-file `sha256` are verified before anything is installed.
- `version.json` is written locally **only** from verified remote metadata, via
  an atomic temp-file rename.
- A downgrade feed is reported, not applied (`allow_downgrade` to override).

## Transactional install

`apply_update` stages every download in `.update_staging/` and journals each
swap to `journal.jsonl` **before** performing it. On any failure the whole patch
rolls back and the exception surfaces; on a crash/power-loss the next launch
(`recover_interrupted_update`) restores every journaled file from its backup, so
the tree is never a mix of two builds. Locked Windows binaries go through the
rename-to-`.old` dance, which is undone if the second rename fails, and stale
`.old` files are swept at startup (`cleanup_old_binaries`).

## Window scaling

All layout lives in a fixed 860x520 logical canvas. The OS window opens at the
largest integer multiple that fits the desktop (up to 2x — 1720x1040 on 4K) and
can be resized freely; `present()` blits nearest-neighbour with letterboxing and
`logical_mouse()` maps cursor position back into canvas space. Buttons and card
plates pre-allocate their translucent surfaces once and re-fill per frame, so
the steady-state draw path allocates nothing.
