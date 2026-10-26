"""Publish an update package and manifest for the Call of Acaristan Launcher.

Generates `dist/update/version.json`, `dist/update/manifest.json` (per-file
SHA-256 hashes for delta patching), and `dist/update/RPE6-<version>.zip`.
You can upload the contents of `dist/update/` to GitHub Releases, Cloudflare
Pages/R2, itch.io, or any static file host.

Usage:
    python tools/publish_update.py --version 0.2.0 --build 4510 \\
        --headline "Patch 0.2.0" --note "Fixed M6 train" --note "UDP polish"
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import socketserver
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parent.parent
INCLUDE_DIRS = ("src", "assets")
INCLUDE_FILES = (
    "acaristan.py",
    "launcher.py",
    "menu_theme.mp3",
    "README.md",
    "pyproject.toml",
    "version.json",
)
EXCLUDE_PARTS = {"__pycache__", ".git", ".update_staging", "graphify-out"}
EXCLUDE_SUFFIX = (".pyc", ".pyo", ".old")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_runtime_files(root: Path):
    for d in INCLUDE_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for dirpath, dirs, files in os.walk(base):
            dirs[:] = sorted(x for x in dirs if x not in EXCLUDE_PARTS)
            for fname in sorted(files):
                if fname.endswith(EXCLUDE_SUFFIX):
                    continue
                full = Path(dirpath) / fname
                rel = full.relative_to(root).as_posix()
                yield rel, full
    for fname in INCLUDE_FILES:
        full = root / fname
        if full.is_file():
            yield fname, full


def _bump_local_files(root: Path, version: str, build: str, headline: str, notes: list[str]) -> None:
    vpath = root / "version.json"
    vdoc = {
        "version": version,
        "build": build,
        "channel": "stable",
        "engine": f"Retardovici Pulse Engine 6 Gold {version}",
        "released_at": time.strftime("%Y-%m-%d"),
        "headline": headline,
        "notes": notes,
    }
    vpath.write_text(json.dumps(vdoc, indent=2) + "\n", encoding="utf-8", newline="\n")

    eng_init = root / "src" / "engine" / "__init__.py"
    if eng_init.is_file():
        txt = eng_init.read_text(encoding="utf-8")
        txt_new = re.sub(r'__version__\s*=\s*"[^"]*"', f'__version__ = "{version}"', txt)
        if txt_new != txt:
            eng_init.write_text(txt_new, encoding="utf-8", newline="\n")


def build_release(
    root: Path,
    version: str,
    build: str,
    headline: str,
    notes: list[str],
    copy_delta_files: bool = False,
    bump_local: bool = False,
) -> Path:
    if bump_local:
        _bump_local_files(root, version, build, headline, notes)

    out_dir = root / "dist" / "update"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_name = f"RPE6-{version}.zip"
    zip_path = out_dir / zip_name
    entries = []

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for rel, full in _iter_runtime_files(root):
            zf.write(full, rel)
            entries.append(
                {
                    "path": rel,
                    "sha256": _sha256(full),
                    "bytes": full.stat().st_size,
                }
            )
            if copy_delta_files:
                dst = out_dir / "files" / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(full, dst)

    zip_sha = _sha256(zip_path)
    zip_size = zip_path.stat().st_size

    manifest = {
        "schema": "ae.package/1",
        "engine": f"Retardovici Pulse Engine 6 Gold {version}",
        "version": version,
        "build": build,
        "zip": zip_name,
        "zip_sha256": zip_sha,
        "zip_bytes": zip_size,
        "files": entries,
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    (out_dir / "manifest.json").write_bytes(manifest_bytes)

    version_doc = {
        "version": version,
        "build": build,
        "channel": "stable",
        "engine": f"Retardovici Pulse Engine 6 Gold {version}",
        "released_at": time.strftime("%Y-%m-%d"),
        "headline": headline,
        "notes": notes,
        "zip_url": zip_name,
        "zip_sha256": zip_sha,
        "zip_bytes": zip_size,
        "manifest_url": "manifest.json",
        # The launcher refuses a manifest whose bytes do not hash to this, so a
        # tampered manifest.json cannot redirect the patch at other files.
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "files_base_url": "files/" if copy_delta_files else "",
    }
    (out_dir / "version.json").write_text(
        json.dumps(version_doc, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(
        f"PUBLISH UPDATE: OK (v{version} build {build}, {len(entries)} files, "
        f"{zip_size / 1e6:.1f} MB -> dist/update/)"
    )
    return out_dir


def serve_directory(directory: Path, port: int) -> None:
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(directory), **kw)
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Serving update feed at http://127.0.0.1:{port}/version.json (Ctrl+C to stop)")
        httpd.serve_forever()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build an update bundle for the KRAPNET Launcher")
    ap.add_argument("--version", default="0.2.0", help="Release version string (e.g. 0.2.0)")
    ap.add_argument("--build", default="4510", help="Build number string (e.g. 4510)")
    ap.add_argument("--headline", default="Call of Acaristan Update", help="Short release title")
    ap.add_argument(
        "--note",
        action="append",
        dest="notes",
        default=[],
        help="Bullet point for changelog (may be passed multiple times)",
    )
    ap.add_argument(
        "--copy-files",
        action="store_true",
        help="Also copy loose files to dist/update/files/ for per-file HTTP delta downloads",
    )
    ap.add_argument(
        "--bump-local",
        action="store_true",
        help="Also update local version.json and src/engine/__init__.py to the new version",
    )
    ap.add_argument(
        "--serve",
        type=int,
        default=0,
        help="After building, serve dist/update/ on localhost:<PORT> for testing",
    )
    args = ap.parse_args(argv)

    notes = args.notes or [
        "Gameplay, visual, and multiplayer stability improvements.",
    ]
    out_dir = build_release(
        ROOT,
        version=args.version,
        build=args.build,
        headline=args.headline,
        notes=notes,
        copy_delta_files=args.copy_files,
        bump_local=args.bump_local,
    )
    if args.serve > 0:
        serve_directory(out_dir, args.serve)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
