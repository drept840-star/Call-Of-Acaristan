"""Build the Windows game as a PyInstaller --onedir bundle (no admin needed).

Usage:  python tools/build_windows.py [--clean]

Output: dist/Call of Acaristan/Call of Acaristan.exe (+ _internal/ folder).
The folder is self-contained: zip it, or run it from any user-writable path.
bore.exe ships once, as part of the assets tree (assets/bin/bore.exe), and is
found at runtime by net.tcp_tunnel.find_bore() via sys._MEIPASS (which is
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
    bore = os.path.join(ROOT, "assets", "bin", "bore.exe")
    if not os.path.isfile(bore):
        print("assets/bin/bore.exe missing")
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
           # assets/ already contains assets/bin/bore.exe: add it ONCE
           # (a separate --add-binary would duplicate it).
           "--add-data", os.path.join(ROOT, "assets") + SEP + "assets",
           "--hidden-import=pygame", "--hidden-import=pygame._sdl2",
           "--collect-all=pygame", "--collect-all=moderngl",
           "--collect-all=glcontext"]
    if "--clean" in argv:
        cmd.append("--clean")
    cmd.append(os.path.join(ROOT, "acaristan.py"))
    if run(cmd):
        return 1
    out = os.path.join(ROOT, "dist", NAME)
    found = [os.path.join(d, "bore.exe") for d, _, f in os.walk(out) if "bore.exe" in f]
    if not found:
        print("BUILD CHECK FAILED: bore.exe not bundled")
        return 1
    print("bundled:", *found, sep="\n  ")
    print("Build complete:", os.path.join(out, NAME + ".exe"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
