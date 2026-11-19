"""wrap_audit.py - every player-facing line through the shared text widgets.

    python tools/wrap_audit.py            # report, exit 1 on any overflow
    python tools/wrap_audit.py -v         # also list each offending string

Harvests every string literal in src/ (AST) and every string in
src/game/content/**/*.json that reads like prose, then lays each one out at
all three radio text sizes in:

* film caption (``speechbox.draw_caption``): block must stay on screen;
  rows past the letterbox band are counted (they grow the band upward);
* speech box (``speechbox.draw_box``): rows past ``MAX_ROWS`` scroll;
* radio (``ui.radio``): rows past ``MAX_ROWS`` scroll;

and flags any single word wider than the widget (it cannot wrap).
"""
import ast
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
os.chdir(ROOT)

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))

from core.config import WIDTH, HEIGHT, LETTER_H  # noqa: E402
from ui import radio as R, speechbox as S  # noqa: E402

PROSE = re.compile(r"^[A-Za-z\"'(\[.\-]")


def _prose(s):
    s = s.strip()
    if len(s) < 25 or " " not in s or not PROSE.match(s):
        return False
    if any(t in s for t in ("def ", "import ", "://", ".py", ".png", "%(", "{0", "\\")):
        return False
    letters = sum(c.isalpha() or c == " " for c in s)
    return letters / len(s) > 0.8


def harvest():
    out = {}
    for p in SRC.rglob("*.py"):
        if "graphify-out" in p.parts:
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        docs = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant):
                    docs.add(id(n.body[0].value))
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs and _prose(n.value):
                out.setdefault(n.value, f"{p.relative_to(ROOT)}:{n.lineno}")
    for p in (SRC / "game" / "content").rglob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        stack = [data]
        while stack:
            v = stack.pop()
            if isinstance(v, dict):
                # authoring notes are never drawn
                stack.extend(x for k, x in v.items() if k.lstrip("_") not in DOC_KEYS)
            elif isinstance(v, list):
                stack.extend(v)
            elif isinstance(v, str) and _prose(v):
                out.setdefault(v, str(p.relative_to(ROOT)))
    # placeholders filled the way ae_text_check does (two digits)
    return {re.sub(r"\{[^{}]*\}", "00", s): w for s, w in out.items()}


DOC_KEYS = {"doc", "docs", "comment", "note", "notes", "description", "about", "readme",
            "source", "addressing"}


def main():
    verbose = "-v" in sys.argv
    strings = harvest()
    screen = pygame.Surface((WIDTH, HEIGHT))
    u = R.unit_for(screen)
    band = LETTER_H
    hard, soft = [], []
    for size in (0, 1, 2):
        R.PREFS["radio_text_size"] = size
        f_cap = R.body_font(None, u)
        f_box = S._fonts(u)[0]
        f_tab = S._fonts(u)[1]
        head = (f_tab.cap + 3) * u + 2 * u
        cap_w = int(WIDTH - 160)
        box_w = WIDTH - 2 * 30 * u - 24 * u
        rad = _radio_metrics(screen)
        for s, where in strings.items():
            rows = S._wrap(s, f_cap, cap_w)
            block = head + len(rows) * f_cap.get_linesize()
            if block + u > HEIGHT:
                hard.append((size, "caption off screen", len(rows), s, where))
            elif block > band - u:
                soft.append((size, f"caption {len(rows)} rows > band", len(rows), s, where))
            for name, font, w in (("caption", f_cap, cap_w), ("box", f_box, box_w),
                                  ("radio", rad["f_body"], rad["text_w"])):
                for word in s.replace("\n", " ").split(" "):
                    if font.size(word)[0] > w:
                        hard.append((size, f"{name} word wider than widget", 0, s, where))
            if size == 1:
                n = len(S._wrap(s, f_box, box_w))
                if n > S.MAX_ROWS:
                    soft.append((size, f"box {n} rows scroll", n, s, where))
            n = len(R._wrap(s, rad["f_body"], rad["text_w"]))
            if n > R.MAX_ROWS:
                soft.append((size, f"radio {n} rows scroll", n, s, where))
    R.PREFS["radio_text_size"] = 1
    kinds = {}
    for size, kind, _n, _s, _w in soft:
        k = re.sub(r"\d+ rows", "N rows", kind)
        kinds[(size, k)] = kinds.get((size, k), 0) + 1
    print(f"strings: {len(strings)}")
    for (size, k), c in sorted(kinds.items()):
        print(f"  info  size={R.SIZE_LABELS[size]:<6} {k}: {c}")
    if verbose:
        for size, kind, _n, s, where in sorted(soft, key=lambda t: (t[0], t[1])):
            print(f"    [{R.SIZE_LABELS[size]}] {kind}  {where}  {s[:70]!r}")
    for size, kind, _n, s, where in hard:
        print(f"  FAIL  size={R.SIZE_LABELS[size]} {kind}  {where}  {s[:70]!r}")
    print("WRAP AUDIT: " + ("FAIL" if hard else "OK"))
    return 1 if hard else 0


def _radio_metrics(screen):
    for v in vars(R).values():
        if isinstance(v, type) and hasattr(v, "metrics") and hasattr(v, "panel_height"):
            return v.metrics(screen)
    raise SystemExit("radio widget metrics not found")


if __name__ == "__main__":
    sys.exit(main())
