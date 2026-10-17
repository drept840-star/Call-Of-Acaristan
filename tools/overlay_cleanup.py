"""Tidy a project root after pasting the slim overlay zip over an older checkout.

Pasting only adds / overwrites files, so leftovers of the old tree stay behind. Two of them matter:

1. Voice clips were converted to OGG (``tools/convert_voice_ogg.py``); the old ``.wav`` twins must go,
   otherwise ``audio.voice`` scans both and the speaker-folder length alignment sees every take twice.
2. Python modules that the refactor moved or deleted (``src/art/m5/*.py`` -> ``src/game/art/m5/``,
   root ``apply_*.py`` helpers, ...) are harmless at runtime but confuse the lint / census tools.

Usage (from the project root, the folder that contains ``acaristan.py``)::

    python tools/overlay_cleanup.py            # dry run: lists what would be removed
    python tools/overlay_cleanup.py --apply    # remove the .wav twins and the stale .py modules

The list of shipped files is ``docs/engine/evidence/overlay_manifest.txt`` (one path per line,
written by the packaging step). Nothing outside ``assets/voice`` (.wav twins) and ``src`` / ``tools``
(.py files missing from the manifest) is ever touched; caches, ``.git``, ``.venv``, ``outputs`` and
your own files elsewhere are left alone.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST = os.path.join(ROOT, "docs", "engine", "evidence", "overlay_manifest.txt")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".ruff_cache", ".pytest_cache"}


def _shipped():
    with open(MANIFEST, encoding="utf-8") as fh:
        return {line.strip().replace("\\", "/") for line in fh if line.strip()}


def _walk(sub):
    base = os.path.join(ROOT, sub)
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            yield os.path.join(dirpath, fn)


def main(argv):
    apply = "--apply" in argv
    shipped = _shipped()
    wav_twins, stale_py = [], []
    for path in _walk(os.path.join("assets", "voice")):
        stem, ext = os.path.splitext(path)
        if ext.lower() == ".wav" and os.path.exists(stem + ".ogg"):
            wav_twins.append(path)
    for sub in ("src", "tools"):
        for path in _walk(sub):
            if not path.endswith(".py"):
                continue
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            if rel not in shipped:
                stale_py.append(path)
    for label, items in (("voice .wav files with an .ogg twin", wav_twins),
                         ("stale .py modules not in the overlay", stale_py)):
        print(f"{len(items)} {label}")
        for p in items:
            print("  " + ("removing " if apply else "would remove ") + os.path.relpath(p, ROOT))
            if apply:
                os.remove(p)
    if not apply and (wav_twins or stale_py):
        print("dry run - re-run with --apply to remove them")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
