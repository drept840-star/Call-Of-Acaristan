"""Keep docs/ARCHITECTURE_MAP.md section 8.1 in sync with assets/3D/.

    python tools/map_assets3d.py           # rewrite the section if out of date
    python tools/map_assets3d.py --check   # exit 1 if out of date (smoke check)
    python tools/map_assets3d.py --start   # background watcher: sync on every add/remove
    python tools/map_assets3d.py --stop    # stop the watcher (it exits within 2 s)
    python tools/map_assets3d.py --watch   # same watcher in the foreground (Ctrl+C stops)

Rows for files still on disk keep their hand-written notes. Rows for removed
files are dropped. New files get an auto row tagged "(auto)":
  B  a tools/ae_import_*.py names the file (fill in the baked id by hand)
  R  something under src/ names it (read at runtime)
  S  nothing does, or only other tools do
The file-count sentence and the stray non-3D sentence are regenerated too.
Run by .githooks/pre-commit and the smoke check map_assets3d.
"""
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets" / "3D"
MAP = ROOT / "docs" / "ARCHITECTURE_MAP.md"
GIT = ROOT / ".git"
BEAT = GIT / "map_assets3d.pid"    # watcher heartbeat, touched every poll
STOP = GIT / "map_assets3d.stop"   # watcher exits when this appears
POLL = 2.0
EXT_3D = {".glb", ".gltf", ".obj", ".fbx", ".bin", ".mtl", ".blend", ".blend1", ".png", ".jpg", ".jpeg"}
HEADER = "| `A/` file | St | Importer / caller -> baked id |\n|---|---|---|\n"
ROW = re.compile(r"^\| `(.+?)` \| (\w) \| (.*) \|$")
COUNT = re.compile(r"`A/` is [^:]*: \d+ files = .*?(?=\. `M/` = )")
STRAY = re.compile(r"(`A/` also holds .*? refs\)\. )?(?=`WP\.ASSETS`)")


def disk_files():
    out = []
    for dp, dn, fn in os.walk(ASSETS):
        dn[:] = sorted(dn)
        for f in fn:
            out.append(Path(dp, f).relative_to(ASSETS).as_posix())
    return sorted(out)


def _ext(name):
    return os.path.splitext(name)[1].lower()


def _sources():
    srcs = {}
    for base in (ROOT / "src", ROOT / "tools"):
        for p in base.rglob("*.py"):
            if "__pycache__" not in p.parts:
                srcs[p.relative_to(ROOT).as_posix()] = p.read_text(encoding="utf-8", errors="replace")
    return srcs


def _refs(name, srcs):
    base = os.path.basename(name)
    stem = os.path.splitext(base)[0]
    keys = (base, '"%s"' % stem, "'%s'" % stem)
    return sorted(p for p, s in srcs.items() if any(k in s for k in keys))


def _short(path):
    for pre, rep in (("src/missions/", ""), ("src/", ""), ("tools/", "T/")):
        if path.startswith(pre):
            return rep + path[len(pre):]
    return path


def auto_row(name, srcs):
    refs = _refs(name, srcs)
    imp = [r for r in refs if re.match(r"tools/ae_import_\w+\.py$", r)]
    run = [r for r in refs if r.startswith("src/")]
    if imp:
        return "B", "%s -> ? (auto: set baked id)" % ", ".join("`%s`" % _short(r) for r in imp)
    if run:
        return "R", "read by %s (auto)" % ", ".join("`%s`" % _short(r) for r in run)
    if refs:
        return "S", "referenced only by %s (auto)" % ", ".join("`%s`" % _short(r) for r in refs)
    return "S", "unimported, no runtime caller (auto)"


def sync(text):
    i = text.index(HEADER) + len(HEADER)
    j = i
    lines = text[i:].split("\n")
    old = {}
    for ln in lines:
        m = ROW.match(ln)
        if not m:
            break
        old[m.group(1)] = (m.group(2), m.group(3))
        j += len(ln) + 1
    files = disk_files()
    srcs = None
    rows, strays = [], []
    for f in files:
        if _ext(f) not in EXT_3D:
            strays.append(f)
            continue
        if f in old:
            st, note = old[f]
        else:
            srcs = srcs or _sources()
            st, note = auto_row(f, srcs)
        rows.append("| `%s` | %s | %s |" % (f, st, note))
    text = text[:i] + "".join(r + "\n" for r in rows) + text[j:]

    c = Counter(_ext(f) or "(none)" for f in files if _ext(f) in EXT_3D)
    parts = ["%d `%s`" % (n, e) for e, n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))]
    sc = Counter(_ext(f) or "(none)" for f in strays)
    parts += ["%d stray `%s`" % (n, e) for e, n in sorted(sc.items())]
    nested = any("/" in f for f in files)
    shape = "nested (has subdirectories)" if nested else "flat (no subdirectories)"
    text = COUNT.sub(lambda m: "`A/` is %s: %d files = %s" % (shape, len(files), ", ".join(parts)), text, 1)

    stray_txt = ""
    if strays:
        srcs = srcs or _sources()
        word = "one stray non-3D file" if len(strays) == 1 else "%d stray non-3D files" % len(strays)
        stray_txt = "`A/` also holds %s: %s. " % (
            word, ", ".join("`%s` (%d refs)" % (f, len(_refs(f, srcs))) for f in strays))
    text = STRAY.sub(lambda m: stray_txt, text, 1)
    return text


def write_sync():
    text = MAP.read_text(encoding="utf-8")
    new = sync(text)
    if new == text:
        return False
    with open(MAP, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new)
    return True


def running():
    try:
        return time.time() - BEAT.stat().st_mtime < POLL * 5
    except OSError:
        return False


def watch():
    STOP.unlink(missing_ok=True)
    BEAT.write_text(str(os.getpid()))
    last = None
    try:
        while not STOP.exists():
            BEAT.touch()
            snap = disk_files()
            if snap != last:
                try:
                    if write_sync():
                        print("MAP ASSETS3D: updated (%d files)" % len(snap), flush=True)
                except Exception as e:  # keep watching; next change retries
                    print("MAP ASSETS3D: sync failed: %s" % e, flush=True)
                last = snap
            time.sleep(POLL)
    except KeyboardInterrupt:
        pass
    finally:
        BEAT.unlink(missing_ok=True)
        STOP.unlink(missing_ok=True)
    return 0


def start():
    if running():
        print("MAP ASSETS3D: watcher already running")
        return 0
    exe = sys.executable
    flags = 0
    if os.name == "nt":
        pw = Path(exe).with_name("pythonw.exe")
        exe = str(pw) if pw.exists() else exe
        flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED, NEW_GROUP, NO_WINDOW
    subprocess.Popen([exe, str(Path(__file__).resolve()), "--watch"], cwd=ROOT,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=flags, start_new_session=os.name != "nt")
    print("MAP ASSETS3D: watcher started (stop: python tools/map_assets3d.py --stop)")
    return 0


def stop():
    if not running():
        print("MAP ASSETS3D: watcher not running")
        BEAT.unlink(missing_ok=True)
        return 0
    STOP.touch()
    print("MAP ASSETS3D: watcher stopping")
    return 0


def main():
    for flag, fn in (("--watch", watch), ("--start", start), ("--stop", stop)):
        if flag in sys.argv:
            return fn()
    if "--check" in sys.argv:
        ok = sync(MAP.read_text(encoding="utf-8")) == MAP.read_text(encoding="utf-8")
        print("MAP ASSETS3D: OK" if ok else "MAP ASSETS3D: STALE - run python tools/map_assets3d.py")
        return 0 if ok else 1
    print("MAP ASSETS3D: updated docs/ARCHITECTURE_MAP.md" if write_sync() else "MAP ASSETS3D: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
