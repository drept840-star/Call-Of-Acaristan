#!/usr/bin/env python3
"""AE PACKAGE - build the distributable game zip.

RPE6 Phase 10 (M4). Packages the runtime tree (launcher, src/,
assets/, top-level media + project files) into
dist/RPE6-<version>.zip plus dist/manifest.json (per-file sha256,
engine identity). Excludes tests, docs, tools, build outputs,
__pycache__ and sandbox oracle sets - the package is the runnable
game, not the development tree.

    python3 tools/ae_package.py            # build
    python3 tools/ae_package.py --check    # verify dist/ against manifest
"""
import hashlib
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INCLUDE_DIRS = ("src", "assets")
INCLUDE_FILES = ("acaristan.py", "menu_theme.mp3", "README.md",
                 "pyproject.toml")
EXCLUDE_PARTS = {"__pycache__", ".git"}
EXCLUDE_SUFFIX = (".pyc", ".pyo")


def _version():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import engine
    return f"{engine.ENGINE_NAME} {engine.__version__}"


def _iter_files():
    for d in INCLUDE_DIRS:
        for dirpath, dirs, files in os.walk(os.path.join(ROOT, d)):
            dirs[:] = [x for x in dirs if x not in EXCLUDE_PARTS]
            for f in sorted(files):
                if f.endswith(EXCLUDE_SUFFIX):
                    continue
                full = os.path.join(dirpath, f)
                yield os.path.relpath(full, ROOT).replace(os.sep, "/"), full
    for f in INCLUDE_FILES:
        full = os.path.join(ROOT, f)
        if os.path.exists(full):
            yield f, full


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build():
    version = _version()
    tag = "RPE6-" + version.rsplit(" ", 1)[-1]
    dist = os.path.join(ROOT, "dist")
    os.makedirs(dist, exist_ok=True)
    zip_path = os.path.join(dist, f"{tag}.zip")
    entries = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=6) as z:
        for rel, full in _iter_files():
            z.write(full, rel)
            entries.append({"path": rel, "sha256": _sha(full),
                            "bytes": os.path.getsize(full)})
    manifest = {"schema": "ae.package/1", "engine": version,
                "zip": os.path.basename(zip_path),
                "zip_sha256": _sha(zip_path),
                "zip_bytes": os.path.getsize(zip_path),
                "files": entries}
    with open(os.path.join(dist, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=1)
        fh.write("\n")
    print(f"AE PACKAGE: OK ({len(entries)} files, "
          f"{manifest['zip_bytes'] / 1e6:.1f} MB -> dist/{manifest['zip']})")
    return 0


def check():
    mpath = os.path.join(ROOT, "dist", "manifest.json")
    with open(mpath, encoding="utf-8") as fh:
        manifest = json.load(fh)
    zip_path = os.path.join(ROOT, "dist", manifest["zip"])
    assert _sha(zip_path) == manifest["zip_sha256"], "zip hash drift"
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
    want = {e["path"] for e in manifest["files"]}
    assert names == want, (sorted(names ^ want)[:5])
    print(f"AE PACKAGE CHECK: OK ({len(want)} files, zip sha256 verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(check() if "--check" in sys.argv else build())
