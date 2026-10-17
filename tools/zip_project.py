"""Zip this project into a single archive, optionally uploading it to Pixeldrain.

Usage:
    py zip_project.py [--output <name.zip>] [--timestamp] [--include-venv] [--no-upload]
    py zip_project.py --slim [--with-tests] [--output <name.zip>] [--no-upload]

The zip is ALWAYS written to disk (default: ``<project-dir-name>.zip`` next to
this file, overwritten each run). The zip is then uploaded to Pixeldrain via
``PUT /api/file/{name}`` and the terminal prints just::

    https://pixeldrain.com/u/<id>
    Download this, extract it and wait.

Pass ``--no-upload`` to only build the zip (prints the local path instead),
``-v`` for full build/upload details. Each successful upload deletes the
previous one of the same variant (tracked in ``.pixeldrain_last_id`` for
full builds, ``.pixeldrain_last_id_slim`` for ``--slim``), so one full and
one slim build live on Pixeldrain at most - uploading slim never kills
your full-build link.

``--slim`` builds a lightweight PLAYABLE bundle instead of the full dev
snapshot. It keeps the runtime essentials (``src/``, ``assets/`` voice/art/
sprites/music, ``sfx_wav/``, launcher + config + docs) and drops the heavy
regenerable/dev-only bulk: ``trailers/``, ``previews/``, ``outputs/``,
``tests/`` golden frames, shot folders, ``tools/m5_r2_shots`` + ``tools/out``,
``assets/voice/_radio_cache/`` (rebuilt automatically on first voice line -
see ``src/audio/voice.py::_load``), nested zips, ``*.mp4``/``*.xz`` dumps,
every ``*.txt`` (patch readmes, voice ``*_matches.txt`` reports and console
dumps; docs stay as ``.md``), logs and local save/settings state. The default
slim output is ``<project-dir-name>-slim.zip`` so it never overwrites the
full snapshot. ``--with-radio-cache`` keeps the pre-rendered radio FX cache
(~28 MiB, faster first mission load, works fully offline).
``--with-tests`` keeps ``tests/`` whole (~40 MiB: unit tests,
``tests/api/engine_api.json``, the golden/loop/replay baselines, scene
traces) and never slim-filters inside it. All-or-nothing on purpose: a bundle
with tests can run the full gate (``python tools/ae_ci.py``) and the
replay-parity oracle after unpacking; without them it is play-only and the
baseline rows would fail on missing oracles.

Pixeldrain requires an API key (anonymous upload is not supported). Provide it
via ``--api-key`` or the ``PIXELDRAIN_API_KEY`` env var. Get one at
https://pixeldrain.com/user/api_keys and use it as the HTTP Basic password.

The key is remembered: passing ``--api-key <key>`` once saves it to the
gitignored ``.pixeldrain_api_key`` file (never zipped), so later runs need no
flag. ``--set-api-key <key>`` only saves the key and exits.
``--no-save-api-key`` uses ``--api-key`` for one run without saving.

What gets zipped: src/, assets/ (incl. sprites/), sfx_wav/, acaristan.py, etc.
Excludes: .git, .venv, __pycache__, *.pyc, build/, dist/, and .gitignore entries.
With --slim: also drops trailers/, previews/, outputs/, tests/, shot folders,
tools/m5_r2_shots + tools/out, assets/voice/_radio_cache/ (auto-regenerated),
assets/bin/bore.exe (re-fetch via tools/download_bore.py), nested zips,
*.mp4/*.xz/*.txt dumps, logs and local save/settings state.
With --slim --with-tests: keeps tests/ complete (nothing inside it is slim-
filtered) so the unpacked bundle can run the full gate.
"""
from __future__ import annotations

import argparse
import base64
import fnmatch
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIXELDRAIN_API = "https://pixeldrain.com/api"
# Remembers the previous upload so it can be deleted on the next run.
# Tracked per variant: uploading --slim replaces only the previous slim
# upload, never the full snapshot link (and vice versa).
LAST_ID_FILE = PROJECT_ROOT / ".pixeldrain_last_id"
LAST_ID_FILE_SLIM = PROJECT_ROOT / ".pixeldrain_last_id_slim"


def last_id_file(slim: bool) -> Path:
    return LAST_ID_FILE_SLIM if slim else LAST_ID_FILE
# Remembers the API key so --api-key only has to be passed once.
API_KEY_FILE = PROJECT_ROOT / ".pixeldrain_api_key"

# Always excluded, even if not in .gitignore.
ALWAYS_EXCLUDE_DIRS = {
    ".git", ".venv", "__pycache__", ".ruff_cache",
    "build", "dist", ".freebuff", ".kilo", ".vscode",
    "_cut_frames", "room_audit_shots", "prop_audit",
}
ALWAYS_EXCLUDE_FILES = {"*.py[cod]", "*$py.class", ".pixeldrain_api_key", ".pixeldrain_last_id",
                        ".pixeldrain_last_id_slim"}

# Extra excludes applied ONLY with --slim (playable bundle, not dev snapshot).
# These are regenerable outputs, dev evidence, or files the game rebuilds /
# re-downloads on demand (radio cache, bore tunnel binary).
SLIM_EXCLUDE_DIRS = {
    "trailers", "previews", "outputs", "shots", "_shots",
    "tests", ".opencode", ".workbuddy-ai",
    "tools/m5_r2_shots", "tools/out",
    "assets/voice/_radio_cache",  # rebuilt by src/audio/voice.py::_load
    "assets/bin",  # bore.exe re-fetched via tools/download_bore.py
}
SLIM_EXCLUDE_FILES = {
    "*.mp4", "*.xz", "*.avi", "*.mov", "*.mkv", "*.mix.wav",
    "*.txt",  # patch readmes, voice *_matches.txt reports, console dumps (docs stay .md)
    "*.log", "*.err",
    "save_data.json*", "settings.json*", "profile*.json*",
    "*.xlsx", "*.patch", "tools/tools.zip",
}


def load_gitignore(root: Path) -> list[str]:
    patterns: list[str] = []
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return patterns
    for line in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        patterns.append(line)
    return patterns


def is_excluded(rel_posix: str, name: str, is_dir: bool, patterns: list[str]) -> bool:
    parts = rel_posix.split("/")
    if any(p in ALWAYS_EXCLUDE_DIRS for p in parts):
        return True
    if not is_dir and any(fnmatch.fnmatch(name, p) for p in ALWAYS_EXCLUDE_FILES):
        return True
    for pat in patterns:
        p = pat.strip("/")
        if pat.endswith("/"):  # directory prefix match
            if rel_posix == p or rel_posix.startswith(p + "/"):
                return True
        elif fnmatch.fnmatch(rel_posix, p) or fnmatch.fnmatch(name, p):
            return True
    return False


def _matches_any(rel_posix: str, name: str, patterns: set[str]) -> bool:
    return any(
        fnmatch.fnmatch(rel_posix, p)
        or fnmatch.fnmatch(name, p)
        or rel_posix == p
        or rel_posix.startswith(p + "/")
        for p in patterns
    )


def iter_files(root: Path, patterns: list[str], include_venv: bool = False, slim: bool = False,
               with_radio_cache: bool = False, with_tests: bool = False):
    slim_dirs = set(SLIM_EXCLUDE_DIRS)
    slim_files = set(SLIM_EXCLUDE_FILES)
    if slim and with_radio_cache:
        # Keep the pre-rendered radio FX cache (~28 MiB): faster first
        # mission load, fully offline. Still drops the bore binary.
        slim_dirs.discard("assets/voice/_radio_cache")
    if slim and with_tests:
        # Gate-capable bundle: tests/ holds every oracle the tools read
        # (tests/unit, tests/api/engine_api.json, tests/golden|loop|replay
        # baselines, tests/data scene traces) - keep the tree whole.
        slim_dirs.discard("tests")
    keep_tests = slim and with_tests
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        rel_posix = rel.as_posix()
        if path.name.endswith(".zip") and path.parent == root:
            continue  # never zip a previous output into itself
        if path.suffix == ".zip":
            # Never nest zips (tools/tools.zip, mission5-W*.zip, ...).
            if path.is_file():
                continue
        if ".venv" in rel.parts and include_venv:
            pass
        elif is_excluded(rel_posix, path.name, path.is_dir(), patterns):
            continue
        # With --with-tests nothing inside tests/ is slim-filtered: the oracle
        # inputs are *.txt (scene traces), *.json (manifests, api snapshot)
        # and *.png (golden frames) and all of them must survive.
        if keep_tests and (rel_posix == "tests" or rel_posix.startswith("tests/")):
            if path.is_file():
                yield path
            continue
        if slim and _matches_any(rel_posix, path.name, slim_dirs if path.is_dir() else slim_dirs | slim_files):
            continue
        # Slim file patterns also apply to files nested under kept dirs
        # (e.g. a stray *.mp4 inside docs/ or tools/).
        if slim and path.is_file() and _matches_any(rel_posix, path.name, slim_files):
            continue
        if path.is_file():
            yield path


def default_output(slim: bool = False) -> Path:
    suffix = "-slim" if slim else ""
    return PROJECT_ROOT / f"{PROJECT_ROOT.name}{suffix}.zip"


def zip_project(output: Path | None, include_venv: bool = False, quiet: bool = False,
                slim: bool = False, with_radio_cache: bool = False,
                with_tests: bool = False) -> Path:
    patterns = load_gitignore(PROJECT_ROOT)
    if output is None:
        output = default_output(slim)
    if output.exists():
        output.unlink()

    count = 0
    top_level: set[str] = set()
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=9) as zf:
        for path in iter_files(PROJECT_ROOT, patterns, include_venv, slim, with_radio_cache, with_tests):
            rel = path.relative_to(PROJECT_ROOT)
            top_level.add(rel.parts[0])
            zf.write(path, rel)
            count += 1
    size_mib = output.stat().st_size / 1_048_576
    if not quiet:
        print(f"Zipped {count} files -> {output} ({size_mib:.2f} MiB)")
        print("Included top level: " + ", ".join(sorted(top_level)))
    return output


def get_api_key(cli_key: str | None) -> str:
    key = (cli_key or "").strip()
    if key:
        return key
    key = (os.environ.get("PIXELDRAIN_API_KEY") or "").strip()
    if key:
        return key
    if API_KEY_FILE.is_file():
        try:
            key = API_KEY_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            key = ""
        if key:
            return key
    raise RuntimeError(
        "Pixeldrain upload needs an API key: pass --api-key <key> once "
        "(it is then saved to .pixeldrain_api_key for future runs), or set "
        "PIXELDRAIN_API_KEY. Get one at https://pixeldrain.com/user/api_keys"
    )


def save_api_key(key: str) -> Path:
    """Persist the API key for future runs (gitignored, never zipped)."""
    key = (key or "").strip()
    if not key:
        raise RuntimeError("Cannot save an empty API key.")
    API_KEY_FILE.write_text(key + "\n", encoding="utf-8")
    try:
        os.chmod(API_KEY_FILE, 0o600)
    except (AttributeError, OSError):
        pass  # Windows / filesystems without chmod - file is still gitignored
    return API_KEY_FILE


def upload_pixeldrain(zip_path: Path, api_key: str) -> dict:
    """PUT the zip to Pixeldrain, return the file-info dict (contains 'id')."""
    name = urllib.parse.quote(zip_path.name)
    url = f"{PIXELDRAIN_API}/file/{name}"
    credentials = base64.b64encode(f":{api_key}".encode()).decode()
    req = urllib.request.Request(
        url,
        data=zip_path.read_bytes(),  # raw body, NOT multipart (per PUT docs)
        method="PUT",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/zip",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            info = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read().decode("utf-8", "replace"))
            detail = f"{err.get('value', '?')}: {err.get('message', '')}".strip()
        except (ValueError, OSError):
            detail = f"HTTP {exc.code}"
        raise RuntimeError(f"Pixeldrain upload failed ({detail})") from exc
    # NOTE: PUT returns the file info directly (no 'success' wrapper, unlike
    # POST), so an 'id' in the response means the upload succeeded.
    if info.get("success") is False or "id" not in info:
        raise RuntimeError(f"Pixeldrain upload failed: {info}")
    return info


def verify_upload(file_id: str) -> dict:
    """GET the file info back to prove the upload really persisted."""
    url = f"{PIXELDRAIN_API}/file/{file_id}/info"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            info = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Pixeldrain verification failed: HTTP {exc.code} for {file_id}") from exc
    if not info.get("success") or info.get("id") != file_id:
        raise RuntimeError(f"Pixeldrain verification failed: {info}")
    return info


def delete_pixeldrain(file_id: str, api_key: str) -> bool:
    """DELETE a previous upload. Returns True if it is gone afterwards.

    A 404 means it was already gone (deleted by hand, expired, ...), which
    counts as success. Other failures return False so the caller can warn
    without failing the whole run - the new upload is already live.
    """
    credentials = base64.b64encode(f":{api_key}".encode()).decode()
    req = urllib.request.Request(
        f"{PIXELDRAIN_API}/file/{file_id}",
        method="DELETE",
        headers={"Authorization": f"Basic {credentials}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return bool(result.get("success"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return True  # already gone
        return False
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Zip the project, optionally upload to Pixeldrain.")
    ap.add_argument("--output", "-o", default=None, help="Output zip path (default: <project-dir-name>.zip, or <project-dir-name>-slim.zip with --slim).")
    ap.add_argument("--timestamp", action="store_true", help="Append a timestamp to the default output name.")
    ap.add_argument("--include-venv", action="store_true", help="Include .venv/ (excluded by default).")
    ap.add_argument("--slim", action="store_true",
                    help="Playable bundle: keep runtime essentials (src/, assets voice/art/sprites/music, "
                         "sfx_wav/, launcher, docs), drop trailers/previews/outputs, tests (unless "
                         "--with-tests), shot folders, radio FX cache (regenerates on first run), *.txt files "
                         "and dump/log files.")
    ap.add_argument("--with-radio-cache", action="store_true",
                    help="With --slim: also pack assets/voice/_radio_cache/ (~28 MiB) for faster first "
                         "mission load / fully offline voice. Ignored without --slim.")
    ap.add_argument("--with-tests", action="store_true",
                    help="With --slim: keep tests/ whole (~40 MiB: unit tests, api snapshot, golden/loop/"
                         "replay baselines, scene traces) so the unpacked bundle can run the full gate "
                         "(tools/ae_ci.py) and the replay-parity oracle. Ignored without --slim.")
    ap.add_argument("--no-upload", action="store_true", help="Only build the zip, skip the Pixeldrain upload.")
    ap.add_argument("--api-key", default=None, help="Pixeldrain API key (saved to .pixeldrain_api_key for future runs).")
    ap.add_argument(
        "--set-api-key",
        default=None,
        metavar="KEY",
        help="Save KEY as the default Pixeldrain API key and exit (no zip/upload).",
    )
    ap.add_argument(
        "--no-save-api-key",
        action="store_true",
        help="Do not persist --api-key; only use it for this run.",
    )
    ap.add_argument("--verbose", "-v", action="store_true", help="Print full build/upload details.")
    args = ap.parse_args(argv)
    verbose = args.verbose

    try:
        if args.set_api_key:
            saved = save_api_key(args.set_api_key)
            print(f"Saved Pixeldrain API key to {saved} (future runs need no --api-key).")
            return 0

        if args.output:
            output = Path(args.output).resolve()
        elif args.timestamp:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = "-slim" if args.slim else ""
            output = PROJECT_ROOT / f"{PROJECT_ROOT.name}{suffix}_{stamp}.zip"
        else:
            output = None  # zip_project() falls back to the stable default name

        zip_path = zip_project(output, include_venv=args.include_venv, quiet=not verbose and not args.no_upload,
                               slim=args.slim, with_radio_cache=args.with_radio_cache, with_tests=args.with_tests)
        if not args.no_upload:
            if (args.api_key or "").strip() and not args.no_save_api_key:
                saved = save_api_key(args.api_key)
                if verbose:
                    print(f"Saved Pixeldrain API key to {saved} (future runs need no --api-key).")
            api_key = get_api_key(args.api_key)
            id_file = last_id_file(args.slim)
            old_id = id_file.read_text(encoding="utf-8").strip() if id_file.is_file() else ""
            info = upload_pixeldrain(zip_path, api_key)
            file_id = info["id"]
            verify_upload(file_id)
            if old_id and old_id != file_id:
                deleted = delete_pixeldrain(old_id, api_key)
                if verbose and deleted:
                    print(f"Deleted previous upload: {old_id}")
                if not deleted:
                    print(f"warning: could not delete previous upload {old_id} (new file is live)", file=sys.stderr)
            id_file.write_text(file_id + "\n", encoding="utf-8")
            if verbose:
                print(f"Verified on Pixeldrain: {info.get('name', zip_path.name)}")
                print(f"Uploaded: {info.get('name', zip_path.name)} ({info.get('size', 0) / 1_048_576:.2f} MiB)")
                print(f"Direct download: {PIXELDRAIN_API}/file/{file_id}")
            print(f"https://pixeldrain.com/u/{file_id}")
            print("Download this, extract it and wait.")
    except (OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
