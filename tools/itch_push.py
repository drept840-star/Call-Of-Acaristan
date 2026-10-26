"""Push a built game to itch.io with butler (the official itch upload CLI).

The itch desktop app auto-updates installed games when a new build lands on
the same channel, applying butler's own delta patches — for itch players that
IS the "I upload a new build, the player receives it" loop, and it is the
delivery path this repo uses for itch distribution. This wrapper makes the
push a one-liner and fails loudly on the common mistakes (butler missing, no
build, malformed target).

Usage:
    python tools/itch_push.py myuser/call-of-acaristan:windows
    python tools/itch_push.py myuser/call-of-acaristan:windows --userversion v0.2.0

One-time setup:
    1. install butler from https://itch.io/docs/butler/ (must be on PATH)
    2. `butler login` once with your itch account

What to push: the PyInstaller onedir from `python tools/build_windows.py`
(`dist/Call of Acaristan`). A zip also works — butler extracts zips — pass it
via --dir. Keep the channel name stable (`windows` here): the app updates a
channel in place, and renaming channels strands installed players.

Saves: `save_data.json`/`settings.json`/`profiles.json` are runtime files that
are not part of any pushed build, and butler patches never remove files it
does not know about (that is why `butler clean` exists for manual pruning), so
player saves survive app updates. Verify with a real channel push before
relying on it for a paying audience.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "dist" / "Call of Acaristan"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Push the built game to itch.io via butler")
    ap.add_argument(
        "target",
        help="itch target as user/game:channel, e.g. myuser/call-of-acaristan:windows",
    )
    ap.add_argument(
        "--dir",
        default=str(DEFAULT_DIR),
        help="directory (or zip) to push; default: dist/Call of Acaristan",
    )
    ap.add_argument(
        "--userversion",
        default="",
        help="human-readable version shown in the itch app (e.g. v0.2.0); "
        "otherwise butler stamps the upload time",
    )
    args = ap.parse_args(argv)

    butler = shutil.which("butler")
    if not butler:
        print("ITCH PUSH FAILED: butler not found on PATH.")
        print("  Install once from https://itch.io/docs/butler/ and run `butler login`.")
        return 1

    target = args.target.strip()
    user_game, _, channel = target.partition(":")
    user, slash, game = user_game.partition("/")
    if not user or not slash or not game or not channel:
        print(f"ITCH PUSH FAILED: target {target!r} must look like 'user/game:channel'.")
        return 1

    push_path = Path(args.dir)
    if not push_path.exists():
        print(f"ITCH PUSH FAILED: {push_path} does not exist.")
        print("  Build first:  python tools/build_windows.py")
        return 1

    cmd = [butler, "push", str(push_path), target]
    if args.userversion:
        cmd += ["--userversion", args.userversion]
    print(">", " ".join(cmd))
    code = subprocess.call(cmd, cwd=str(ROOT))

    if code == 0:
        print(f"ITCH PUSH: OK — https://{user}.itch.io/{game} (channel '{channel}')")
        print("  The itch app offers this build to installed players automatically.")
    else:
        print("ITCH PUSH FAILED: butler exited non-zero (auth? run `butler login`).")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
