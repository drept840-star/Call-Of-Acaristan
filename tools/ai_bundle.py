"""Bundle whole files or line slices into one paste-ready block for an external chat AI.

    python tools/ai_bundle.py src/app.py:1244-1295 src/ui/credits.py
    python tools/ai_bundle.py --no-clip src/app.py:1-80     # stdout only

Each argument is `path` or `path:start-end` (1-based, inclusive; `path:start-` runs to EOF).
Prints `N lines, M files` to stderr, the bundle to stdout, and copies it to the clipboard
(`clip` on Windows, `pbcopy` / `xclip` elsewhere) unless --no-clip is given.
Slice line numbers are the real file line numbers (a `--- START OF FILE path (lines a-b of n) ---` header).
Pair with the slice table in docs/ARCHITECTURE_MAP.md section 20.1.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARG = re.compile(r"^(.*?)(?::(\d*)-(\d*))?$")


def parse(arg):
    m = ARG.match(arg)
    path, a, b = m.group(1), m.group(2), m.group(3)
    if re.fullmatch(r"[A-Za-z]", path):      # a bare drive letter: the colon belonged to the path
        path, a, b = arg, None, None
    return path, (int(a) if a else None), (int(b) if b else None), m.group(2) is not None


def bundle(args):
    out, total = [], 0
    for arg in args:
        path, a, b, sliced = parse(arg)
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        if not p.is_file():
            raise SystemExit("ai_bundle: no such file: %s" % path)
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        n = len(lines)
        lo, hi = max(1, a or 1), min(n, b or n)
        if lo > hi:
            raise SystemExit("ai_bundle: empty range %s (file has %d lines)" % (arg, n))
        chunk = lines[lo - 1:hi]
        total += len(chunk)
        try:
            shown = p.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            shown = p.as_posix()
        tag = "" if (lo, hi) == (1, n) else " (lines %d-%d of %d)" % (lo, hi, n)
        out.append("--- START OF FILE %s%s ---\n%s\n--- END OF FILE %s ---\n" % (shown, tag, "\n".join(chunk), shown))
    return "\n".join(out), total


def to_clipboard(text):
    cmds = [["clip"]] if os.name == "nt" else [["pbcopy"], ["xclip", "-selection", "clipboard"], ["wl-copy"]]
    for c in cmds:
        if shutil.which(c[0]):
            data = text.encode("utf-16-le") if c[0] == "clip" else text.encode("utf-8")
            try:
                subprocess.run(c, input=data, check=True)
                return True
            except (OSError, subprocess.CalledProcessError):
                pass
    return False


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args or "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return 2
    text, total = bundle(args)
    copied = "--no-clip" not in sys.argv and to_clipboard(text)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(text)
    print("ai_bundle: %d lines, %d files%s" % (total, len(args), ", copied to clipboard" if copied else ""),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
