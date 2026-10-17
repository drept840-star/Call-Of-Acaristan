
"""Shared atomic JSON persistence helpers for save_data.json / settings.json.

Writes go to a temp file first, the previous file is kept as ``.bak``, and the
temp file is atomically renamed into place - a crash mid-write can never leave
a truncated/corrupt save as the only copy. Loads fall back to the backup.
"""
import json
import os


def atomic_write(path, obj, indent=2):
    """Write *obj* as pretty JSON to *path* atomically (tmp + bak + replace)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent)
        f.flush()
        os.fsync(f.fileno())
    if os.path.exists(path):
        try:
            with open(path, "rb") as src, open(path + ".bak", "wb") as bak:
                bak.write(src.read())
        except OSError:
            pass  # Backup is best-effort; the atomic replace below still stands.
    os.replace(tmp, path)


def load_with_backup(path, default):
    """Parse JSON at *path*; on missing/corrupt file fall back to ``path.bak``.

    *default* is a zero-arg callable returning a fresh default structure.
    Returns the default if neither file parses.
    """
    for candidate in (path, path + ".bak"):
        if not os.path.exists(candidate):
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue
    return default()
