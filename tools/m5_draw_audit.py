"""Compatibility wrapper: the per-mission draw census is tools/ae_draw_audit.py.

    python tools/ae_draw_audit.py --mission m5 [--min 6]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ae_draw_audit import main  # noqa: E402

if __name__ == "__main__":
    extra = ["--min", sys.argv[1]] if len(sys.argv) > 1 else []
    sys.exit(main(["--mission", "m5"] + extra))
