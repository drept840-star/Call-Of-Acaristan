"""Call of Acaristan — Pre-Game Launcher & Auto-Updater entry point.

Usage:
    python launcher.py                 # Open the KRAPNET Launcher window
    python launcher.py --demo-update   # Test with a simulated v0.2.0 update notice
    python launcher.py --check-only    # Check for updates in the terminal and exit
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Call of Acaristan KRAPNET Launcher")
    parser.add_argument(
        "--demo-update",
        action="store_true",
        help="Start a local mock update server (v0.2.0) to preview the notice and one-click patcher",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Check for updates headlessly and print the status",
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="Do not spawn the game when PLAY GAME is clicked",
    )
    args = parser.parse_args(argv)

    from launcher import (
        DemoUpdateServer,
        check_for_updates,
        itch_receipt_path,
        load_launcher_config,
        play_requires_update,
        recover_interrupted_update,
        run_launcher,
    )

    if args.check_only:
        server = None
        try:
            cfg = load_launcher_config(ROOT)
            if args.demo_update:
                server = DemoUpdateServer(ROOT)
                cfg["update_url"] = server.start()
            recovered = recover_interrupted_update(ROOT)
            if recovered != "none":
                print(f"[RECOVERED] interrupted update: {recovered}")
            res = check_for_updates(ROOT, cfg)
            print(f"[{res.status.upper()}] {res.message}")
            if res.remote and res.status == "update_available":
                print(f"  Headline : {res.remote.headline}")
                print(f"  Changed  : {len(res.remote.changed_files)} file(s)")
                if res.remote.protected_files:
                    print(f"  Protected: {len(res.remote.protected_files)} file(s) kept")
                if res.remote.locally_modified:
                    print(f"  WARNING  : {len(res.remote.locally_modified)} locally modified "
                          f"file(s) would be replaced: {', '.join(res.remote.locally_modified[:5])}")
                print(f"  PLAY will: {'apply the update first' if play_requires_update(res, cfg) else 'launch directly'}")
            if res.refused_reason:
                print(f"  Refused  : {res.refused_reason}")
            if res.status == "unconfigured" and itch_receipt_path(ROOT) is not None:
                print("  Note     : itch.io install detected — updates are "
                      "delivered by the itch app (butler push)")
            return 0
        finally:
            if server is not None:
                server.stop()

    return run_launcher(ROOT, demo_update=args.demo_update, no_launch=args.no_launch)


if __name__ == "__main__":
    raise SystemExit(main())
