"""Build the standalone desktop apps in tools/ into self-contained exes under apps/.

    python tools/build_apps.py              # build every app
    python tools/build_apps.py ai_bundle    # build one

Each app is one Python file plus (optionally) an .ico of the same name. The build
is --onefile --windowed, so the exe drops next to the other tools in apps/ and
finds the project by walking up to the nearest .git. Icons are added as data as
well, because the window icon is loaded at runtime from sys._MEIPASS.

Apps:
    ai_bundle   tools/ai_bundle_app.py    -> apps/AIBundle.exe
    paste_apply tools/paste_apply.py      -> apps/PasteApply.exe
"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
APPS = {
    "ai_bundle": ("tools/ai_bundle_app.py", "AIBundle"),
    "paste_apply": ("tools/paste_apply.py", "PasteApply"),
}


def build(key, clean=False):
    src, name = APPS[key]
    icon = os.path.join(ROOT, "tools", key + ".ico")
    work = os.path.join(ROOT, "build", "apps", key)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
           "--name", name,
           "--distpath", os.path.join(ROOT, "apps"),
           "--workpath", work, "--specpath", work,
           "--paths", os.path.join(ROOT, "tools")]
    if os.path.isfile(icon):
        cmd += ["--icon", icon, "--add-data", icon + (os.pathsep + ".")]
    if clean:
        cmd.append("--clean")
    cmd.append(os.path.join(ROOT, src))
    print(">", " ".join(cmd))
    if subprocess.call(cmd, cwd=ROOT):
        return 1
    out = os.path.join(ROOT, "apps", name + ".exe")
    if not os.path.isfile(out):
        print("BUILD CHECK FAILED: %s missing" % out)
        return 1
    print("built:", out, "(%.1f MB)" % (os.path.getsize(out) / 1048576.0))
    return 0


def main(argv):
    keys = [a for a in argv if not a.startswith("--")] or list(APPS)
    for key in keys:
        if key not in APPS:
            print("unknown app %r; choose from: %s" % (key, ", ".join(APPS)))
            return 2
    for key in keys:
        if build(key, clean="--clean" in argv):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
