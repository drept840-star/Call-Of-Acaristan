"""Build the Windows game as a PyInstaller --onedir bundle (no admin needed).

Usage:  python tools/build_windows.py [--clean]

Output: dist/Call of Acaristan/Call of Acaristan.exe (+ _internal/ folder).
The folder is self-contained: zip it, or run it from any user-writable path.
bore.exe and playitd.exe (the playit.gg agent) ship once, as part of the assets tree (assets/bin), and are
found at runtime by net.tcp_tunnel.find_bundled() via sys._MEIPASS (which is
<exe dir>/_internal on PyInstaller 6) or the executable's own directory.
Nothing is extracted to a temp dir (onedir) and nothing is installed system-wide.
"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NAME = "Call of Acaristan"
SEP = ";" if os.name == "nt" else ":"


def run(cmd):
    print(">", " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


def main(argv):
    if run([sys.executable, os.path.join("tools", "download_bore.py")]):
        return 1
    if run([sys.executable, os.path.join("tools", "download_playit.py")]):
        return 1
    for exe in ("bore.exe", "playitd.exe"):
        if not os.path.isfile(os.path.join(ROOT, "assets", "bin", exe)):
            print("assets/bin/%s missing" % exe)
            return 1
    # --user keeps the install out of system site-packages: no admin rights.
    if run([sys.executable, "-m", "pip", "install", "--user", "--upgrade",
            "pyinstaller", "--quiet"]):
        return 1
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm",
           "--onedir", "--windowed", "--name", NAME,
           "--distpath", os.path.join(ROOT, "dist"),
           "--workpath", os.path.join(ROOT, "build"),
           "--specpath", os.path.join(ROOT, "build"),
           "--paths", os.path.join(ROOT, "src"),
           "--icon", os.path.join(ROOT, "assets", "logo.ico"),
           # assets/ already contains assets/bin/*.exe: add them ONCE
           # (a separate --add-binary would duplicate it).
           "--add-data", os.path.join(ROOT, "assets") + SEP + "assets",
           "--hidden-import=pygame", "--hidden-import=pygame._sdl2",
           "--collect-all=pygame", "--collect-all=moderngl",
           "--collect-all=glcontext"]
    # Missions, cutscenes and adapters are imported by name at runtime, and the
    # authored content (meshes, levels, timelines) sits beside the code in src/:
    # bundle every package whole plus each non-Python file at its src path.
    # (--collect-submodules runs before src/ is on the spec's path, so the
    # modules are listed here instead.)
    src = os.path.join(ROOT, "src")
    for d, dirs, files in os.walk(src):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", "graphify-out")]
        rel = os.path.relpath(d, src)
        pkg = "" if rel == "." else rel.replace(os.sep, ".") + "."
        is_pkg = rel == "." or os.path.isfile(os.path.join(d, "__init__.py"))
        for f in files:
            if f.endswith(".py"):
                if not is_pkg:
                    continue
                mod = pkg + f[:-3]
                if mod.endswith(".__init__"):
                    mod = mod[:-9]
                if mod not in ("__init__", "app"):
                    cmd.append("--hidden-import=" + mod)
            elif not f.endswith(".pyc"):
                cmd += ["--add-data", os.path.join(d, f) + SEP + rel]
    if "--clean" in argv:
        cmd.append("--clean")
    cmd.append(os.path.join(ROOT, "acaristan.py"))
    if run(cmd):
        return 1
    out = os.path.join(ROOT, "dist", NAME)
    found = []
    for exe in ("bore.exe", "playitd.exe"):
        hits = [os.path.join(d, exe) for d, _, f in os.walk(out) if exe in f]
        if not hits:
            print("BUILD CHECK FAILED: %s not bundled" % exe)
            return 1
        found += hits
    for cfg_name in ("version.json", "launcher_config.json"):
        src_cfg = os.path.join(ROOT, cfg_name)
        if os.path.isfile(src_cfg):
            import shutil
            shutil.copy2(src_cfg, os.path.join(out, cfg_name))
    launcher_bat = os.path.join(out, "Call of Acaristan Launcher.bat")
    with open(launcher_bat, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write('@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0Call of Acaristan.exe" --launcher\r\n')
    print("bundled:", *found, sep="\n  ")
    print("Build complete:", os.path.join(out, NAME + ".exe"))
    print("Launcher entry:", launcher_bat)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
