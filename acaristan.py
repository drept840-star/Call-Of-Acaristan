"""Thin launcher — run with `python acaristan.py` from the repo root.

Game lives in src/app.py (runs on import). Keep CWD at repo root so
CWD-relative assets (menu_theme.mp3, assets/, save_data.json) resolve.
Pass `--launcher` (or run `python launcher.py`) to open the pre-game
KRAPNET Launcher & Auto-Updater window before starting the game.
"""
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent
    src_dir = str(ROOT / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

try:
    os.chdir(ROOT)
except OSError:
    pass


def _write_crash_log():
    import traceback

    candidates = [Path(sys.executable).resolve().parent / "crash.txt"]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "CallOfAcaristan" / "crash.txt")
    for path in candidates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                traceback.print_exc(file=fh)
            return
        except OSError:
            continue


if "--launcher" in sys.argv and os.environ.get("ACA_FROM_LAUNCHER") != "1":
    from launcher import run_launcher
    raise SystemExit(run_launcher(ROOT, demo_update=("--demo-update" in sys.argv)))

if not getattr(sys, "frozen", False):
    import app  # noqa: F401  (runs the game on import)
else:
    # Windowed build: no console, so a crash leaves crash.txt beside the exe.
    try:
        import app  # noqa: F401
    except SystemExit:
        raise
    except BaseException:
        _write_crash_log()
        raise
