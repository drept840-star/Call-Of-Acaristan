"""Compatibility wrapper: the Mission 5 bake moved to the generic pipeline.

    python tools/ae_bake.py --pack m5 [--sheet out.png] [--check] [--lint]

Kept so older notes/scripts that call ``tools/bake_m5_sprites.py`` still work.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ae_bake import main  # noqa: E402

if __name__ == "__main__":
    argv = ["--pack", "m5"] + sys.argv[1:]
    sys.exit(main(argv))
