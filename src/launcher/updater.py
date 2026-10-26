"""Update checker and in-place patcher for Call of Acaristan.

Supports two update transport styles without requiring the player to manually
download a new installer or .exe from a browser:
  1. Delta / Manifest mode (`manifest.json` with per-file SHA-256 hashes):
     Compares local files against remote hashes and downloads/extracts ONLY
     changed files.
  2. Release Archive mode (`version.json` or GitHub Releases `.zip`):
     Streams the release zip into `.update_staging/`, verifies SHA-256 when
     provided, and swaps updated files into place while preserving player
     saves (`save_data.json`, `settings.json`, `profiles.json`).

Trust model (see `docs/LAUNCHER.md`):
  * Every URL that is actually fetched must be HTTPS, unless its host is
    explicitly allow-listed as a local/dev feed (`allow_insecure_hosts`, or a
    loopback address). Plain-HTTP release feeds are refused, not warned about.
  * A feed that advertises `manifest_sha256` must deliver a manifest whose
    bytes hash to that value; a feed that advertises `zip_sha256` must deliver
    a matching archive. A mismatch aborts the update before anything is written.
  * `version.json` is written locally only from metadata that was part of a
    verified payload, and it is written atomically.
  * A remote version older than the local one is reported as a downgrade and is
    never applied by the normal update path.

Overwrite protection: files listed in the config `protect` key or in a
`.aca_skip` / `.aca_skip.json` file at the install root are never replaced.
Files that look locally modified (mtime newer than the installed build stamp)
are reported on the result object so the launcher can warn instead of silently
clobbering a hotfix.

On Windows, locked binaries (`.exe`, `.dll`, `.pyd`) can be replaced in-place
by renaming the active file to `<name>.old` before moving the new file in;
stale `.old` files are swept on the next launcher startup. Every replacement is
recorded in a journal (`.update_staging/journal.jsonl`) so an interrupted patch
can be rolled back or completed on the next run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import re
import shutil
import socketserver
import threading
import time
from typing import Callable
import urllib.error
import urllib.parse
import urllib.request
import zipfile

DEFAULT_PRESERVE = (
    "save_data.json",
    "settings.json",
    "profiles.json",
    "launcher_config.json",
)

# Files the launcher itself owns; never treated as "locally modified" noise and
# never useful to patch over a user's config.
DEFAULT_PROTECT = (
    "save_data.json",
    "save_data*.json",
    "settings.json",
    "profiles.json",
    "launcher_config.json",
    ".aca_skip",
    ".aca_skip.json",
)

SKIP_FILE_NAMES = (".aca_skip", ".aca_skip.json")

# Hosts allowed to serve plain HTTP. Loopback is always allowed (demo feed);
# anything else must be named in `launcher_config.json: allow_insecure_hosts`.
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}

# Substrings that mean "this is a local edit", not "this is a stale build".
_INTERESTING_LOCAL_EDIT_SUFFIXES = (
    ".py", ".json", ".ini", ".cfg", ".toml", ".txt", ".md", ".bat", ".ps1", ".sh",
)

STAGING_DIR_NAME = ".update_staging"
JOURNAL_NAME = "journal.jsonl"

ProgressCallback = Callable[[str, float, str], None]


class UpdateError(RuntimeError):
    """A refused or failed update. Never raised for 'no update available'."""


class InsecureTransport(UpdateError):
    """A URL was refused because it is not HTTPS and its host is not allow-listed."""


class IntegrityError(UpdateError):
    """A downloaded payload did not match its advertised SHA-256."""


@dataclass
class LocalVersion:
    version: str = "0.1.0"
    build: str = "4471"
    channel: str = "stable"
    engine: str = "Retardovici Pulse Engine 6 Gold 0.1.0"
    released_at: str = "2026-10-26"
    headline: str = "Call of Acaristan"
    notes: list[str] = field(default_factory=list)

    @property
    def display_tag(self) -> str:
        return f"v{self.version} // BUILD {self.build}"


@dataclass
class RemoteFileEntry:
    path: str
    sha256: str
    bytes: int
    url: str = ""


@dataclass
class RemoteUpdateInfo:
    version: str
    build: str = ""
    headline: str = ""
    notes: list[str] = field(default_factory=list)
    released_at: str = ""
    zip_url: str = ""
    zip_sha256: str = ""
    zip_bytes: int = 0
    manifest_url: str = ""
    manifest_sha256: str = ""
    files_base_url: str = ""
    files: list[RemoteFileEntry] = field(default_factory=list)
    changed_files: list[RemoteFileEntry] = field(default_factory=list)
    protected_files: list[str] = field(default_factory=list)
    locally_modified: list[str] = field(default_factory=list)

    @property
    def display_tag(self) -> str:
        if self.build:
            return f"v{self.version} (BUILD {self.build})"
        return f"v{self.version}"

    @property
    def download_bytes(self) -> int:
        if self.changed_files and self.files_base_url:
            return sum(f.bytes for f in self.changed_files)
        if self.zip_bytes > 0:
            return self.zip_bytes
        if self.changed_files:
            return sum(f.bytes for f in self.changed_files)
        return 0


@dataclass
class UpdateCheckResult:
    status: str  # "up_to_date" | "update_available" | "unconfigured" | "offline" | "refused"
    local: LocalVersion
    remote: RemoteUpdateInfo | None = None
    message: str = ""
    checked_at: float = field(default_factory=time.time)
    # Populated when the feed itself is untrustworthy (HTTP, bad manifest hash).
    refused_reason: str = ""


def parse_version_tuple(version_str: str, build_str: str = "") -> tuple[int, ...]:
    """Convert ('0.2.0', '4510') into a comparable integer tuple (0, 2, 0, 4510)."""
    clean = str(version_str or "0.0.0").strip().lstrip("vV")
    nums = [int(x) for x in re.findall(r"\d+", clean)[:4]]
    while len(nums) < 3:
        nums.append(0)
    build_nums = re.findall(r"\d+", str(build_str or ""))
    build_int = int(build_nums[0]) if build_nums else 0
    return (*nums[:3], build_int)


def is_newer_version(
    remote_ver: str,
    remote_build: str,
    local_ver: str,
    local_build: str,
) -> bool:
    rv = parse_version_tuple(remote_ver, remote_build)
    lv = parse_version_tuple(local_ver, local_build)
    # If remote does not specify a build number, compare only (major, minor, patch)
    if not str(remote_build or "").strip():
        return rv[:3] > lv[:3]
    return rv > lv


def is_downgrade(
    remote_ver: str,
    remote_build: str,
    local_ver: str,
    local_build: str,
) -> bool:
    """True when the remote feed is strictly OLDER than what is installed."""
    rv = parse_version_tuple(remote_ver, remote_build)
    lv = parse_version_tuple(local_ver, local_build)
    if not str(remote_build or "").strip():
        return rv[:3] < lv[:3]
    return rv < lv


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def format_bytes(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "unknown size"
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024.0:.1f} KB"
    return f"{num_bytes / (1024.0 * 1024.0):.1f} MB"


# ── Transport policy ─────────────────────────────────────────────────────────


def url_host(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def is_insecure_url(url: str) -> bool:
    """True when `url` is plain HTTP (i.e. not https, file, or loopback)."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    scheme = (parts.scheme or "").lower()
    if scheme in ("https", "file"):
        return False
    if scheme != "http":
        return False
    return (parts.hostname or "").lower() not in _LOOPBACK_HOSTS


def ensure_trusted_url(url: str, config: dict | None = None) -> str:
    """Refuse plain-HTTP release feeds unless the host is allow-listed.

    Loopback hosts are always allowed so `--demo-update` and local static
    servers keep working; any other host must be named in the config key
    ``allow_insecure_hosts`` (list of hostnames or ``*.suffix`` patterns).
    """
    if not url:
        return url
    cfg = config or {}
    if not is_insecure_url(url):
        return url
    host = url_host(url)
    allowed = cfg.get("allow_insecure_hosts") or []
    if isinstance(allowed, str):
        allowed = [allowed]
    for pattern in allowed:
        pat = str(pattern).strip().lower()
        if not pat:
            continue
        if pat == host or fnmatch.fnmatch(host, pat):
            return url
    raise InsecureTransport(
        f"refused insecure HTTP feed {host or url!r}: use HTTPS, "
        f"or add the host to launcher_config.json 'allow_insecure_hosts'"
    )


# ── Local version / config ───────────────────────────────────────────────────


def cleanup_old_binaries(root: Path) -> int:
    """Delete leftover `*.old` files created during Windows in-place updates."""
    removed = 0
    for p in root.rglob("*.old"):
        try:
            if p.is_file():
                p.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def load_local_version(root: Path) -> LocalVersion:
    vpath = root / "version.json"
    if vpath.is_file():
        try:
            data = json.loads(vpath.read_text(encoding="utf-8"))
            notes = data.get("notes") or []
            if isinstance(notes, str):
                notes = [ln.strip() for ln in notes.splitlines() if ln.strip()]
            return LocalVersion(
                version=str(data.get("version") or "0.1.0"),
                build=str(data.get("build") or "4471"),
                channel=str(data.get("channel") or "stable"),
                engine=str(data.get("engine") or "Retardovici Pulse Engine 6 Gold 0.1.0"),
                released_at=str(data.get("released_at") or ""),
                headline=str(data.get("headline") or "Call of Acaristan"),
                notes=[str(x) for x in notes],
            )
        except Exception:
            pass
    return LocalVersion()


def save_local_version(root: Path, info: RemoteUpdateInfo, prev: LocalVersion) -> LocalVersion:
    """Write `version.json` atomically from *verified* remote metadata."""
    updated = LocalVersion(
        version=info.version or prev.version,
        build=info.build or prev.build,
        channel=prev.channel,
        engine=f"Retardovici Pulse Engine 6 Gold {info.version or prev.version}",
        released_at=info.released_at or time.strftime("%Y-%m-%d"),
        headline=info.headline or prev.headline,
        notes=list(info.notes) if info.notes else list(prev.notes),
    )
    payload = {
        "version": updated.version,
        "build": updated.build,
        "channel": updated.channel,
        "engine": updated.engine,
        "released_at": updated.released_at,
        "headline": updated.headline,
        "notes": updated.notes,
    }
    vpath = root / "version.json"
    tmp = vpath.with_name(vpath.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, vpath)
    return updated


def itch_receipt_path(root: Path) -> Path | None:
    """Path of the itch app's install receipt, when the game was installed by it.

    The itch desktop app extracts each game into its own folder and drops
    ``.itch/receipt.json`` there. Detecting it lets the launcher step aside:
    on an itch-managed install, updates are delivered by the itch app itself
    (butler delta patches), and a second in-launcher patcher would only race
    the app for the same files. Returns ``None`` for any other install.
    """
    for base in (root, *root.parents[:2]):
        receipt = base / ".itch" / "receipt.json"
        if receipt.is_file():
            return receipt
    return None


def load_launcher_config(root: Path) -> dict:
    cfg = {
        "update_url": "",
        "github_repo": "",
        "check_on_startup": True,
        "timeout_seconds": 4.0,
        "preserve_files": list(DEFAULT_PRESERVE),
        "protect": [],
        "allow_insecure_hosts": [],
        "allow_downgrade": False,
    }
    cpath = root / "launcher_config.json"
    if cpath.is_file():
        try:
            loaded = json.loads(cpath.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except Exception:
            pass
    env_url = os.environ.get("ACA_UPDATE_URL", "").strip()
    env_repo = os.environ.get("ACA_GITHUB_REPO", "").strip()
    if env_url:
        cfg["update_url"] = env_url
    if env_repo:
        cfg["github_repo"] = env_repo
    return cfg


def load_protected_patterns(root: Path, config: dict | None = None) -> list[str]:
    """Combine `protect` config, `.aca_skip(.json)` files and the built-ins.

    `.aca_skip` is one path (or glob) per line, `#` comments allowed.
    `.aca_skip.json` is `{"protect": ["src/missions/m6/train3d.py", ...]}`.
    """
    cfg = config or {}
    patterns: list[str] = list(DEFAULT_PROTECT)
    raw = cfg.get("protect") or []
    if isinstance(raw, str):
        raw = [raw]
    patterns.extend(str(p) for p in raw if str(p).strip())

    plain = root / SKIP_FILE_NAMES[0]
    if plain.is_file():
        try:
            for line in plain.read_text(encoding="utf-8").splitlines():
                line = line.split("#", 1)[0].strip()
                if line:
                    patterns.append(line)
        except OSError:
            pass
    js = root / SKIP_FILE_NAMES[1]
    if js.is_file():
        try:
            data = json.loads(js.read_text(encoding="utf-8"))
            extra = data.get("protect") if isinstance(data, dict) else data
            if isinstance(extra, str):
                extra = [extra]
            for p in extra or []:
                if str(p).strip():
                    patterns.append(str(p))
        except (OSError, ValueError):
            pass
    return patterns


def _norm_rel(path: str) -> str:
    return str(path).replace("\\", "/").lstrip("/")


def _is_protected(rel_path: str, patterns: list[str], preserve: set[str]) -> bool:
    norm = _norm_rel(rel_path)
    name = Path(norm).name
    if norm in preserve or name in preserve:
        return True
    if _is_preserved(norm, preserve):
        return True
    for pattern in patterns:
        pat = _norm_rel(pattern)
        if not pat:
            continue
        if fnmatch.fnmatch(norm, pat) or fnmatch.fnmatch(name, pat):
            return True
        # A bare directory name protects the whole subtree.
        if not any(ch in pat for ch in "*?[") and norm.startswith(pat.rstrip("/") + "/"):
            return True
    return False


# ── Fetching ─────────────────────────────────────────────────────────────────


def _fetch_json(url: str, timeout: float = 4.0, config: dict | None = None) -> dict:
    ensure_trusted_url(url, config)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CallOfAcaristan-Launcher/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def _compute_changed_files(
    root: Path,
    entries: list[RemoteFileEntry],
    preserve: set[str],
    patterns: list[str] | None = None,
) -> tuple[list[RemoteFileEntry], list[RemoteFileEntry], list[str]]:
    """Return (changed, locally_modified, protected_paths)."""
    pats = patterns or list(DEFAULT_PROTECT)
    changed: list[RemoteFileEntry] = []
    modified: list[RemoteFileEntry] = []
    protected: list[str] = []
    for entry in entries:
        rel_norm = _norm_rel(entry.path)
        if _is_protected(rel_norm, pats, preserve):
            protected.append(rel_norm)
            continue
        local_path = root / rel_norm
        if not local_path.is_file():
            changed.append(entry)
            continue
        try:
            size_differs = local_path.stat().st_size != entry.bytes and entry.bytes > 0
            hash_differs = (not size_differs) and sha256_file(local_path).lower() != entry.sha256.lower()
        except OSError:
            changed.append(entry)
            continue
        if size_differs or hash_differs:
            changed.append(entry)
            if _looks_locally_modified(local_path, root):
                modified.append(entry)
    return changed, modified, protected


def _looks_locally_modified(local_path: Path, root: Path) -> bool:
    """Heuristic: a tracked text file newer than the install stamp is a local edit.

    The install stamp is the mtime of `version.json` (written by the last
    successful update / publish). Any tracked file touched after it, with a
    text-ish suffix, is probably a hotfix someone made on purpose - the
    launcher surfaces those instead of silently overwriting them.
    """
    if local_path.suffix.lower() not in _INTERESTING_LOCAL_EDIT_SUFFIXES:
        return False
    stamp = root / "version.json"
    try:
        if not stamp.is_file():
            return False
        return local_path.stat().st_mtime > stamp.stat().st_mtime + 1.0
    except OSError:
        return False


def _parse_manifest_entries(manifest_data: dict, base_url: str = "") -> list[RemoteFileEntry]:
    out: list[RemoteFileEntry] = []
    for item in manifest_data.get("files") or []:
        if not isinstance(item, dict):
            continue
        rel = _norm_rel(item.get("path") or "")
        sha = str(item.get("sha256") or "")
        size = int(item.get("bytes") or 0)
        file_url = str(item.get("url") or "")
        if not file_url and base_url and rel:
            file_url = urllib.parse.urljoin(base_url.rstrip("/") + "/", rel)
        if rel and sha:
            out.append(RemoteFileEntry(path=rel, sha256=sha, bytes=size, url=file_url))
    return out


def _fetch_manifest(
    manifest_url: str,
    inline_data: dict | None,
    expected_sha256: str,
    timeout: float,
    config: dict | None,
) -> dict | None:
    """Fetch a manifest and verify it against the advertised digest when present."""
    if manifest_url:
        ensure_trusted_url(manifest_url, config)
        req = urllib.request.Request(
            manifest_url,
            headers={"User-Agent": "CallOfAcaristan-Launcher/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        if expected_sha256:
            actual = sha256_bytes(raw)
            if actual.lower() != expected_sha256.lower():
                raise IntegrityError(
                    f"manifest SHA-256 mismatch (feed said {expected_sha256[:12]}…, "
                    f"got {actual[:12]}…)"
                )
        return json.loads(raw.decode("utf-8"))
    if inline_data is not None and expected_sha256:
        # Inline manifest in version.json: hash the canonical form we parsed.
        actual = sha256_bytes(json.dumps(inline_data, sort_keys=True).encode("utf-8"))
        if actual.lower() != expected_sha256.lower():
            raise IntegrityError("inline manifest SHA-256 mismatch")
    return inline_data


def _check_via_url(
    url: str,
    root: Path,
    local: LocalVersion,
    timeout: float,
    preserve: set[str],
    config: dict | None = None,
) -> RemoteUpdateInfo:
    cfg = config or {}
    ensure_trusted_url(url, cfg)
    data = _fetch_json(url, timeout=timeout, config=cfg)
    base_dir_url = url.rsplit("/", 1)[0] + "/" if "/" in url else ""

    # Support both `version.json` and direct `ae.package/1` `manifest.json`
    version = str(data.get("version") or "")
    if not version and "engine" in data:
        # e.g. "Retardovici Pulse Engine 6 Gold 0.2.0"
        parts = str(data["engine"]).rsplit(" ", 1)
        version = parts[-1] if parts else "0.1.0"
    build = str(data.get("build") or "")
    headline = str(data.get("headline") or f"Call of Acaristan v{version}")
    raw_notes = data.get("notes") or []
    if isinstance(raw_notes, str):
        notes = [ln.strip(" -*\t") for ln in raw_notes.splitlines() if ln.strip()]
    else:
        notes = [str(n) for n in raw_notes]

    zip_url = str(data.get("zip_url") or data.get("zip") or "")
    if zip_url and not zip_url.startswith(("http://", "https://")):
        zip_url = urllib.parse.urljoin(base_dir_url, zip_url)
    zip_sha256 = str(data.get("zip_sha256") or "")
    zip_bytes = int(data.get("zip_bytes") or 0)

    manifest_url = str(data.get("manifest_url") or "")
    if manifest_url and not manifest_url.startswith(("http://", "https://")):
        manifest_url = urllib.parse.urljoin(base_dir_url, manifest_url)
    manifest_sha256 = str(data.get("manifest_sha256") or "")

    files_base_url = str(data.get("files_base_url") or "")
    if files_base_url and not files_base_url.startswith(("http://", "https://")):
        files_base_url = urllib.parse.urljoin(base_dir_url, files_base_url)

    inline_manifest = data if "files" in data else None
    manifest_data = _fetch_manifest(
        manifest_url, inline_manifest, manifest_sha256, timeout, cfg
    )

    files: list[RemoteFileEntry] = []
    changed: list[RemoteFileEntry] = []
    modified: list[RemoteFileEntry] = []
    protected: list[str] = []
    if manifest_data:
        if not zip_url and manifest_data.get("zip"):
            zrel = str(manifest_data["zip"])
            zip_url = urllib.parse.urljoin(manifest_url or base_dir_url, zrel)
        if not zip_sha256 and manifest_data.get("zip_sha256"):
            zip_sha256 = str(manifest_data["zip_sha256"])
        if not zip_bytes and manifest_data.get("zip_bytes"):
            zip_bytes = int(manifest_data["zip_bytes"])
        files = _parse_manifest_entries(manifest_data, files_base_url)
        patterns = load_protected_patterns(root, cfg)
        changed, modified, protected = _compute_changed_files(root, files, preserve, patterns)

    return RemoteUpdateInfo(
        version=version or local.version,
        build=build,
        headline=headline,
        notes=notes,
        released_at=str(data.get("released_at") or ""),
        zip_url=zip_url,
        zip_sha256=zip_sha256,
        zip_bytes=zip_bytes,
        manifest_url=manifest_url,
        manifest_sha256=manifest_sha256,
        files_base_url=files_base_url,
        files=files,
        changed_files=changed,
        protected_files=protected,
        locally_modified=[f.path for f in modified],
    )


def _check_via_github(
    repo: str,
    root: Path,
    local: LocalVersion,
    timeout: float,
    preserve: set[str],
    config: dict | None = None,
) -> RemoteUpdateInfo:
    cfg = config or {}
    api_url = f"https://api.github.com/repos/{repo.strip('/')}/releases/latest"
    rel = _fetch_json(api_url, timeout=timeout, config=cfg)
    tag = str(rel.get("tag_name") or rel.get("name") or "").lstrip("vV")
    # Support optional build tag like "v0.2.0+4510" or "0.2.0-4510"
    version = tag
    build = ""
    if "+" in tag:
        version, build = tag.split("+", 1)
    elif "-" in tag and tag.rsplit("-", 1)[-1].isdigit():
        version, build = tag.rsplit("-", 1)

    headline = str(rel.get("name") or f"Release v{version}")
    body = str(rel.get("body") or "")
    notes = [
        ln.strip(" -*#\t")
        for ln in body.splitlines()
        if ln.strip() and not ln.strip().startswith("```")
    ][:8]

    zip_url = ""
    zip_bytes = 0
    manifest_url = ""
    version_json_url = ""
    for asset in rel.get("assets") or []:
        name = str(asset.get("name") or "")
        dl_url = str(asset.get("browser_download_url") or "")
        if name == "version.json":
            version_json_url = dl_url
        elif name == "manifest.json":
            manifest_url = dl_url
        elif name.lower().endswith(".zip") and not zip_url:
            zip_url = dl_url
            zip_bytes = int(asset.get("size") or 0)

    if version_json_url:
        return _check_via_url(version_json_url, root, local, timeout, preserve, cfg)

    files: list[RemoteFileEntry] = []
    changed: list[RemoteFileEntry] = []
    modified: list[RemoteFileEntry] = []
    protected: list[str] = []
    zip_sha256 = ""
    if manifest_url:
        try:
            mdata = _fetch_manifest(manifest_url, None, "", timeout, cfg)
            if mdata:
                zip_sha256 = str(mdata.get("zip_sha256") or "")
                files = _parse_manifest_entries(mdata, "")
                patterns = load_protected_patterns(root, cfg)
                changed, modified, protected = _compute_changed_files(
                    root, files, preserve, patterns
                )
        except IntegrityError:
            raise
        except Exception:
            pass

    return RemoteUpdateInfo(
        version=version or local.version,
        build=build,
        headline=headline,
        notes=notes,
        released_at=str(rel.get("published_at") or "")[:10],
        zip_url=zip_url,
        zip_sha256=zip_sha256,
        zip_bytes=zip_bytes,
        manifest_url=manifest_url,
        files=files,
        changed_files=changed,
        protected_files=protected,
        locally_modified=[f.path for f in modified],
    )


def check_for_updates(root: Path, config: dict | None = None) -> UpdateCheckResult:
    """Check configured remote feed and compare against local version."""
    local = load_local_version(root)
    cfg = config if config is not None else load_launcher_config(root)
    timeout = float(cfg.get("timeout_seconds") or 4.0)
    preserve = set(cfg.get("preserve_files") or DEFAULT_PRESERVE)

    update_url = str(cfg.get("update_url") or "").strip()
    github_repo = str(cfg.get("github_repo") or "").strip()

    if not update_url and not github_repo:
        return UpdateCheckResult(
            status="unconfigured",
            local=local,
            remote=None,
            message=f"LOCAL BUILD READY // {local.display_tag}",
        )

    try:
        if update_url:
            remote = _check_via_url(update_url, root, local, timeout, preserve, cfg)
        else:
            remote = _check_via_github(github_repo, root, local, timeout, preserve, cfg)
    except (InsecureTransport, IntegrityError) as exc:
        return UpdateCheckResult(
            status="refused",
            local=local,
            remote=None,
            message=f"FEED REFUSED // {exc}",
            refused_reason=str(exc),
        )
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return UpdateCheckResult(
            status="offline",
            local=local,
            remote=None,
            message=f"RELAY OFFLINE ({type(exc).__name__}) // LOCAL {local.display_tag}",
        )

    if not bool(cfg.get("allow_downgrade", False)) and is_downgrade(
        remote.version, remote.build, local.version, local.build
    ):
        return UpdateCheckResult(
            status="up_to_date",
            local=local,
            remote=remote,
            message=(
                f"FEED IS OLDER ({remote.display_tag}) // KEEPING {local.display_tag}"
            ),
        )

    newer = is_newer_version(remote.version, remote.build, local.version, local.build)
    if newer:
        return UpdateCheckResult(
            status="update_available",
            local=local,
            remote=remote,
            message=f"NEW VERSION AVAILABLE: {remote.display_tag}",
        )

    return UpdateCheckResult(
        status="up_to_date",
        local=local,
        remote=remote,
        message=f"UP TO DATE // {local.display_tag}",
    )


# ── Install / rollback ───────────────────────────────────────────────────────


def _is_preserved(rel_path: str, preserve: set[str]) -> bool:
    norm = _norm_rel(rel_path)
    name = Path(norm).name
    if norm in preserve or name in preserve:
        return True
    if name.startswith("save_data") and name.endswith(".json"):
        return True
    if name.startswith("settings") and name.endswith(".json"):
        return True
    if name.startswith("profiles") and name.endswith(".json"):
        return True
    return False


class _InstallJournal:
    """Append-only record of file replacements, used to roll back a failed patch.

    Each successful swap appends one JSON line:
        {"dst": "<relative path>", "backup": "<relative path or ''>", "staged": "<rel>"}
    ``backup`` is the ``.old`` sidecar for locked Windows binaries, or a copy in
    ``.update_staging/backup/`` for ordinary files. ``rollback()`` walks the
    journal backwards and restores every backup.
    """

    def __init__(self, staging: Path, install_root: Path):
        self.staging = staging
        self.install_root = install_root
        self.path = staging / JOURNAL_NAME
        self.backup_dir = staging / "backup"
        self._entries: list[dict] = []

    def _abs(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else self.install_root / p

    def record(self, dst: Path, backup: Path | None) -> None:
        """Journal one intended swap. Written BEFORE the swap, so a crash at any
        later point (including between the two renames of a locked binary) can
        always be undone by ``rollback``."""
        def _rel(p: Path) -> str:
            return str(p.relative_to(self.install_root)).replace("\\", "/")

        entry = {"dst": _rel(dst), "backup": _rel(backup) if backup is not None else ""}
        self._entries.append(entry)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(entry) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        except OSError:
            pass

    def rollback(self) -> int:
        """Restore every journaled file; returns how many were restored.

        * entry has a backup that still exists -> move it back over the target
          (this also repairs a half-done swap of a locked binary).
        * entry was marked ``new`` -> the file did not exist before the patch,
          so delete it.
        * otherwise -> the target was never touched; nothing to do.
        """
        restored = 0
        for entry in reversed(self._entries):
            dst = self._abs(entry["dst"])
            backup = self._abs(entry["backup"]) if entry.get("backup") else None
            if backup is not None and backup.is_file():
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(backup, dst)
                    restored += 1
                except OSError:
                    pass
            elif entry.get("new") and dst.is_file():
                try:
                    dst.unlink()
                    restored += 1
                except OSError:
                    pass
        self._entries.clear()
        return restored

    def mark_last_new(self) -> None:
        """Flag the most recent entry as 'file did not exist before this patch'."""
        if not self._entries:
            return
        self._entries[-1]["new"] = True
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            if lines:
                lines[-1] = json.dumps(self._entries[-1])
                self.path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        except OSError:
            pass


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def recover_interrupted_update(install_root: Path) -> str:
    """Finish or undo a patch that was interrupted by a crash / power loss.

    Called by the launcher before it checks for updates. Returns a short status
    string for logging: ``"none"``, ``"rolled_back"`` or ``"left_staged"``.
    A staging directory with no journal is just a stale download and is
    removed; one with a journal is rolled back so the install is never a mix of
    two versions.
    """
    staging = install_root / STAGING_DIR_NAME
    if not staging.is_dir():
        return "none"
    journal_path = staging / JOURNAL_NAME
    if not journal_path.is_file():
        shutil.rmtree(staging, ignore_errors=True)
        return "none"
    entries: list[dict] = []
    try:
        for line in journal_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        return "left_staged"
    journal = _InstallJournal(staging, install_root)
    journal._entries = entries
    restored = journal.rollback()
    shutil.rmtree(staging, ignore_errors=True)
    return "rolled_back" if restored else "none"


def _safe_replace_file(src_file: Path, dst_file: Path, backup: Path | None = None) -> Path | None:
    """Replace ``dst_file`` with ``src_file``; return the backup path (or None).

    Ordinary files: the old content is copied to ``backup`` *before* the swap, so
    a crash can always restore it. Locked Windows binaries: the running file is
    renamed to ``<name>.old`` (Windows allows renaming an open exe) and that
    rename is the backup - if the second move fails the first is undone, so the
    target is never left missing.
    """
    dst_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        if backup is not None and dst_file.is_file():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst_file, backup)
        os.replace(src_file, dst_file)
        return backup if (backup is not None and backup.is_file()) else None
    except PermissionError:
        # On Windows, a running .exe or loaded .dll cannot be overwritten directly,
        # but CAN be renamed to .old while open. The backup copy above (if any)
        # stays valid; `.old` is the move-aside sidecar that makes the swap legal.
        old_backup = dst_file.with_suffix(dst_file.suffix + ".old")
        try:
            if old_backup.exists():
                old_backup.unlink()
        except OSError:
            pass
        moved_old = False
        try:
            os.replace(dst_file, old_backup)
            moved_old = True
            os.replace(src_file, dst_file)
        except OSError:
            if moved_old:
                # Undo the first rename so the install still has a working file.
                try:
                    os.replace(old_backup, dst_file)
                except OSError:
                    pass
            raise
        if backup is not None and backup.is_file():
            return backup
        return old_backup


def _swap_journaled(journal: "_InstallJournal", src_file: Path, dst_file: Path) -> None:
    """Journal a swap *before* performing it, then swap.

    Order matters: the journal line is flushed first, so a crash between the two
    renames of a locked binary leaves a record that ``recover_interrupted_update``
    can repair on the next launch. A file that did not exist before the patch is
    journalled with no backup, and rollback deletes it.
    """
    rel_dst = _norm_rel(str(dst_file.relative_to(journal.install_root)))
    existed = dst_file.is_file()
    backup = journal.backup_dir / rel_dst if existed else None
    journal.record(dst_file, backup)
    _safe_replace_file(src_file, dst_file, backup=backup)
    if not existed:
        journal.mark_last_new()


def _download_stream(
    url: str,
    dest: Path,
    timeout: float,
    expected_bytes: int = 0,
    on_chunk: Callable[[int, int], None] | None = None,
    config: dict | None = None,
) -> int:
    ensure_trusted_url(url, config)
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CallOfAcaristan-Launcher/1.0"},
    )
    total_read = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content_len = int(resp.headers.get("Content-Length") or expected_bytes or 0)
        with open(dest, "wb") as out:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out.write(chunk)
                total_read += len(chunk)
                if on_chunk:
                    on_chunk(total_read, content_len)
    return total_read


def apply_update(
    root: Path,
    info: RemoteUpdateInfo,
    config: dict | None = None,
    progress_cb: ProgressCallback | None = None,
    target_root: Path | None = None,
    force: bool = False,
) -> LocalVersion:
    """Download and apply `info` in-place.

    If `target_root` is given (e.g. during `--demo-update` sandbox testing),
    files are written into `target_root` instead of modifying the repo tree.

    The install is transactional: every replaced file is journaled first, and a
    failure mid-apply rolls the whole patch back before re-raising, so the tree
    is never a mix of two versions.
    """
    cfg = config if config is not None else load_launcher_config(root)
    timeout = max(10.0, float(cfg.get("timeout_seconds") or 4.0) * 3.0)
    preserve = set(cfg.get("preserve_files") or DEFAULT_PRESERVE)
    patterns = load_protected_patterns(root, cfg)
    install_root = target_root if target_root is not None else root
    staging = install_root / STAGING_DIR_NAME

    def report(stage: str, frac: float, detail: str) -> None:
        if progress_cb is not None:
            progress_cb(stage, max(0.0, min(1.0, frac)), detail)

    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    journal = _InstallJournal(staging, install_root)
    journal.backup_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Mode 1: Per-file delta update if changed_files have individual URLs
        delta_candidates = [f for f in info.changed_files if f.url]
        if delta_candidates:
            total_bytes = sum(max(1, f.bytes) for f in delta_candidates)
            done_bytes = 0
            staged_pairs: list[tuple[Path, Path]] = []

            for idx, entry in enumerate(delta_candidates, 1):
                rel = _norm_rel(entry.path)
                if _is_preserved(rel, preserve) or _is_protected(rel, patterns, preserve):
                    continue
                staged_path = staging / "files" / rel
                report(
                    "DOWNLOADING DELTA",
                    done_bytes / max(1, total_bytes),
                    f"[{idx}/{len(delta_candidates)}] {rel}",
                )

                def _chunk_cb(cur: int, _tot: int, base: int = done_bytes, r: str = rel) -> None:
                    report(
                        "DOWNLOADING DELTA",
                        (base + cur) / max(1, total_bytes),
                        f"Downloading {r} ({format_bytes(base + cur)} / {format_bytes(total_bytes)})",
                    )

                _download_stream(
                    entry.url,
                    staged_path,
                    timeout=timeout,
                    expected_bytes=entry.bytes,
                    on_chunk=_chunk_cb,
                    config=cfg,
                )
                if entry.sha256:
                    actual_sha = sha256_file(staged_path)
                    if actual_sha.lower() != entry.sha256.lower():
                        raise IntegrityError(f"SHA-256 mismatch for {rel}")
                done_bytes += max(1, entry.bytes)
                staged_pairs.append((staged_path, install_root / rel))

            for idx, (src_p, dst_p) in enumerate(staged_pairs, 1):
                report("APPLYING PATCH", idx / max(1, len(staged_pairs)), f"Updating {dst_p.name}")
                _swap_journaled(journal, src_p, dst_p)

        elif info.zip_url:
            # Mode 2: Download release zip and extract changed / non-preserved files
            zip_file = staging / "release_update.zip"
            report("DOWNLOADING PACKAGE", 0.02, f"Connecting to {info.display_tag} package...")

            def _zip_chunk(cur: int, tot: int) -> None:
                denom = max(1, tot or info.zip_bytes or cur)
                report(
                    "DOWNLOADING PACKAGE",
                    0.05 + 0.65 * (cur / denom),
                    f"Downloading {format_bytes(cur)} / {format_bytes(denom)}",
                )

            _download_stream(
                info.zip_url,
                zip_file,
                timeout=timeout,
                expected_bytes=info.zip_bytes,
                on_chunk=_zip_chunk,
                config=cfg,
            )

            if info.zip_sha256:
                report("VERIFYING PACKAGE", 0.72, "Checking SHA-256 signature...")
                actual = sha256_file(zip_file)
                if actual.lower() != info.zip_sha256.lower():
                    raise IntegrityError("Package SHA-256 verification failed")

            changed_set = {_norm_rel(f.path) for f in info.changed_files}
            extract_root = staging / "extracted"
            with zipfile.ZipFile(zip_file, "r") as zf:
                members = [m for m in zf.infolist() if not m.is_dir()]
                for idx, member in enumerate(members, 1):
                    rel = _norm_rel(member.filename)
                    if not rel or ".." in Path(rel).parts:
                        continue
                    if _is_preserved(rel, preserve) or _is_protected(rel, patterns, preserve):
                        continue
                    # If we have a manifest delta list, only extract files that actually changed!
                    if changed_set and rel not in changed_set:
                        continue
                    frac = 0.75 + 0.23 * (idx / max(1, len(members)))
                    report("APPLYING UPDATE", frac, f"Patching {rel}")
                    extracted_path = extract_root / rel
                    extracted_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member, "r") as src_fh, open(extracted_path, "wb") as dst_fh:
                        shutil.copyfileobj(src_fh, dst_fh)
                    _swap_journaled(journal, extracted_path, install_root / rel)
        else:
            raise ValueError("Remote update metadata did not include a download URL")

        prev_ver = load_local_version(root)
        new_ver = save_local_version(install_root, info, prev_ver)
        report("UPDATE COMPLETE", 1.0, f"Updated to {new_ver.display_tag}")
        return new_ver
    except BaseException:
        # Anything that goes wrong after the first swap rolls the patch back.
        if journal._entries:
            report("ROLLING BACK", 0.0, "Restoring files from the pre-update backup...")
            journal.rollback()
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


class DemoUpdateServer:
    """Local HTTP server that hosts a simulated v0.2.0 update for testing the Launcher."""

    def __init__(self, root: Path):
        self.root = root
        self.port = 0
        self._httpd: socketserver.TCPServer | None = None
        self._thread: threading.Thread | None = None
        self._payloads: dict[str, tuple[bytes, str]] = {}
        self._build_demo_payloads()

    def _build_demo_payloads(self) -> None:
        local = load_local_version(self.root)
        parts = [int(x) for x in re.findall(r"\d+", local.version)[:3]]
        while len(parts) < 3:
            parts.append(0)
        demo_ver = f"{parts[0]}.{parts[1] + 1}.0"
        demo_build = str(int(re.findall(r"\d+", local.build)[0]) + 39) if re.findall(r"\d+", local.build) else "4510"

        # Create a small in-memory zip + delta file so the progress bar and SHA-256 verifier run for real
        readme_bytes = (
            f"# Call of Acaristan {demo_ver} (Build {demo_build})\n"
            "Applied seamlessly via the KRAPNET Pre-Flight Launcher.\n"
        ).encode("utf-8")
        patch_note_bytes = json.dumps(
            {
                "patched_by": "KRAPNET Launcher",
                "version": demo_ver,
                "build": demo_build,
            },
            indent=2,
        ).encode("utf-8")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("PATCH_NOTES_LATEST.md", readme_bytes)
            zf.writestr("assets/update_stamp.json", patch_note_bytes)
        zip_bytes = buf.getvalue()
        zip_sha = hashlib.sha256(zip_bytes).hexdigest()

        manifest = {
            "schema": "ae.package/1",
            "engine": f"Retardovici Pulse Engine 6 Gold {demo_ver}",
            "zip": f"RPE6-{demo_ver}.zip",
            "zip_sha256": zip_sha,
            "zip_bytes": len(zip_bytes),
            "files": [
                {
                    "path": "PATCH_NOTES_LATEST.md",
                    "sha256": hashlib.sha256(readme_bytes).hexdigest(),
                    "bytes": len(readme_bytes),
                },
                {
                    "path": "assets/update_stamp.json",
                    "sha256": hashlib.sha256(patch_note_bytes).hexdigest(),
                    "bytes": len(patch_note_bytes),
                },
            ],
        }
        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
        version_doc = {
            "version": demo_ver,
            "build": demo_build,
            "channel": "stable",
            "released_at": "2026-10-26",
            "headline": "KRAPNET Relay Patch — Delta Updater & Netcode Polish",
            "notes": [
                "Seamless in-launcher delta patching (no manual .exe re-downloads)",
                "Preserves save_data.json, settings.json, and operator profiles",
                "UDP fast-path telemetry & automatic reconnect improvements",
                "Mission 6 Whiteout shader & viewmodel lighting adjustments",
            ],
            "zip_url": f"RPE6-{demo_ver}.zip",
            "zip_sha256": zip_sha,
            "zip_bytes": len(zip_bytes),
            "manifest_url": "manifest.json",
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "files_base_url": "files/",
        }

        self._payloads["/version.json"] = (json.dumps(version_doc, indent=2).encode("utf-8"), "application/json")
        self._payloads["/manifest.json"] = (manifest_bytes, "application/json")
        self._payloads[f"/RPE6-{demo_ver}.zip"] = (zip_bytes, "application/zip")
        self._payloads["/files/PATCH_NOTES_LATEST.md"] = (readme_bytes, "text/markdown")
        self._payloads["/files/assets/update_stamp.json"] = (patch_note_bytes, "application/json")

    @property
    def version_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/version.json"

    def start(self) -> str:
        payloads = self._payloads

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                clean_path = self.path.split("?", 1)[0]
                if clean_path in payloads:
                    body, ctype = payloads[clean_path]
                    # Brief artificial latency so the user can see the progress bar animate smoothly
                    time.sleep(0.18)
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, fmt, *args):
                return

        class _ReusableTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        self._httpd = _ReusableTCPServer(("127.0.0.1", 0), _Handler)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self.version_url

    def stop(self) -> None:
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None
