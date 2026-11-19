"""AI Bundle - paste an AI's file request, get the requested files on the clipboard.

The AI writes a list like

    - src/entities/
        - weapons.py - switch_weapon, reload/fire/melee gating

    (Plus the slices from src/missions/m{1..6}/draw3d.py.)

and the app resolves every path against the project, reads it, and copies one
paste-ready block with a header naming each file:

    --- START OF FILE src/entities/weapons.py ---
    ...
    --- END OF FILE src/entities/weapons.py ---

Usage:
    python tools/ai_bundle_app.py                   GUI
    python tools/ai_bundle_app.py --check FILE      parse FILE, print the manifest
    python tools/ai_bundle_app.py --message-file FILE --out bundle.txt [--clip]
    python tools/ai_bundle_app.py --selftest        parse the built-in example

Files longer than 800 lines (the AI's own rule) are sliced by the names it asks
for: matching `def`/`class`/module constants, the enclosing `class` header, and
the import prologue, with each part labelled by its real line numbers. A file
whose names cannot be resolved is sent whole - never half a file with no match.
Same header syntax as `python tools/ai_bundle.py`, so the two are interchangeable.

Build the exe (output: apps/AIBundle.exe):
    python tools/build_apps.py ai_bundle
"""
import ast
import json
import os
import re
import sys
import time
from pathlib import Path

APP_NAME = "AI Bundle"
EXE_NAME = "AIBundle"
SLICE_LINES = 800           # files longer than this get name slices, not the whole file
LEAD_LIMIT = 60             # prologue cap when a file has no imports
FULL_COVER = 0.62           # if the slices cover this much of a file, send it whole
RARE = 3                    # a word matching at most this many symbols is "specific"
GAP = 2                     # merge ranges separated by at most this many lines

FROZEN = getattr(sys, "frozen", False)
HERE = Path(sys.executable if FROZEN else __file__).resolve().parent


def project_of(d):
    """Nearest folder above d holding .git, so the exe can live in apps/."""
    p = Path(d)
    while not (p / ".git").is_dir():
        if p.parent == p:
            return Path(d)
        p = p.parent
    return p


ROOT = project_of(HERE)
DATA = Path(os.environ.get("APPDATA") or Path.home()) / "AIBundle"
SETTINGS = DATA / "settings.json"

EXT = (".py", ".pyi", ".json", ".md", ".txt", ".toml", ".cfg", ".ini", ".yml", ".yaml",
       ".bat", ".ps1", ".glsl", ".vert", ".frag", ".css", ".html", ".js", ".ts", ".tsx",
       ".csv", ".rst", ".sh")
# {0,255} keeps the scan linear on long dotted runs; \.? keeps .wolf/ style hidden dirs
PATH_RE = re.compile(r"(?<![\w\-])(?<!://)((?:[A-Za-z]:)?\.?[A-Za-z0-9_][A-Za-z0-9_./\\-]{0,255}\.(?:%s))(?![\w])"
                     % "|".join(e[1:] for e in EXT), re.I)
RANGE_RE = re.compile(r"^:(\d*)\s*-\s*(\d*)")
BULLET_RE = re.compile(r"^[\s>]*(?:[-*+\u2022]|\d+[.)])\s+")
ID_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
DOT_ID_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)")
SHORT = {"core": "src/core", "entities": "src/entities", "game": "src/game", "ui": "src/ui",
         "missions": "src/missions", "engine": "src/engine", "audio": "src/audio",
         "fx": "src/fx", "cutscenes": "src/cutscenes", "art": "src/art", "net": "src/net",
         "content": "src/game/content"}   # mN/... is handled by _shorthand
# the bundlers themselves, and words too generic to be a symbol request
RESERVED = {"tools/ai_bundle.py", "tools/ai_bundle_app.py"}
FILLER = {"file", "files", "full", "whole", "only", "helper", "helpers", "and", "the", "for",
          "with", "from", "this", "that", "these", "those", "into", "over", "plus", "also",
          "gating", "fields", "logic", "timers", "attributes", "current", "shared",
          "existing", "minimal", "bundle", "please", "share", "using", "code", "lines",
          "slices", "slice", "parts", "part", "check", "within", "above", "below"}
ACTOR_WORDS = {"player", "pose", "weapon", "hold", "cast", "melee", "molotov", "reload",
               "swap", "switch", "animation"}
# the helpers that draw the player/held weapon in a missions/mN/draw3d.py scene
ACTOR_NAMES = {"_player_pose", "_draw_player", "_draw_cast", "_draw_actor", "_player_hum",
               "player_hum", "_draw_hands", "_draw_arms", "_draw_weapon", "_draw_held"}

SAMPLE = """To design and implement a proper weapon-switching animation across 2.5D
(entities.weapons.switch_weapon + topdown3d / mN/draw3d.py + arena_view3d.py)
and 3D (m8/revenge/trap3d.py + m7/raid3d.py shared _player_pose), I need to
inspect the current swap logic, timers, and player/weapon pose drawing.

Please share the following minimal bundle (using named-function/class slices for
the >800-line files since they don't have section anchors):

  - src/core/
      - state.py - STATE.reset() weapon/reload/swap fields.
  - src/entities/
      - player.py - full file (player state, movement, reload/attack, weapon
        rig/timers).
      - weapons.py - switch_weapon, reload/fire/melee gating, and weapon state
        attributes.
  - src/game/
      - topdown3d.py - full file (shared 2.5D host for M1-M6 and MP arena).
  - src/missions/m1/
      - draw3d.py - player pose, weapon/molotov hold, and player draw helper
        only.
  - src/missions/m2/
      - draw3d.py - player pose, weapon hold, and player draw helper only.
  - src/missions/m3/
      - draw3d.py - player pose, melee/weapon hold, and player draw helper only.
  - src/missions/m4/
      - draw3d.py - player pose, weapon hold, and player draw helper only.
  - src/missions/m5/
      - draw3d.py - player pose, weapon hold, and player draw helper only.
  - src/missions/m6/
      - draw3d.py - player pose, weapon hold, and player draw helper only.
      - yard3d.py - YardScene input/update/player pose/weapon draw (to check
        whether any secondary/melee swap exists).
  - src/missions/m7/
      - raid3d.py - RaidScene._player_pose, player/weapon draw, update, and
        handle_event (borrowed by TrapScene).
  - src/missions/m8/revenge/
      - trap3d.py - WPN_SPECS, _switch_weapon, _sync_weapon_attrs,
        TrapScene.update, handle_event, and player/weapon drawing.
      - trap_hud.py - full file (how HUD displays active weapon/reload/swap
        state).
  - src/ui/
      - arena_view3d.py - full file (2.5D MP player weapon/pose draw).

Copy-paste bundle for the <=800-line files:

python tools/ai_bundle.py src/core/state.py src/entities/player.py
src/game/topdown3d.py src/missions/m8/revenge/trap_hud.py src/ui/arena_view3d.py

(Plus the weapon/player-pose/draw slices from src/entities/weapons.py,
src/missions/m{1..6}/draw3d.py, src/missions/m6/yard3d.py,
src/missions/m7/raid3d.py, and src/missions/m8/revenge/trap3d.py.)
"""


# ---------------------------------------------------------------- path parsing
def expand_braces(text, budget=400):
    """m{1..6}/x.py and {a,b}.py -> one line per expansion."""
    out = []
    for line in text.splitlines():
        todo = [line]
        while todo and budget > 0:
            cur = todo.pop(0)
            budget -= 1
            m = re.search(r"\{([^{}]+)\}", cur)
            if not m or budget <= 0:
                out.append(cur)
                continue
            body = m.group(1)
            nums = re.fullmatch(r"\s*(-?\d{1,9})\s*\.\.\s*(-?\d{1,9})\s*", body)
            if nums:
                a, b = int(nums.group(1)), int(nums.group(2))
                step = 1 if b >= a else -1
                picks = [str(n) for n in range(a, b + step, step)[:200]]
            elif re.fullmatch(r"[^{}]*,[^{}]*", body):
                picks = [x.strip() for x in body.split(",")][:200]
            else:
                out.append(cur)
                continue
            todo[:0] = [cur[:m.start()] + p + cur[m.end():] for p in picks]
        out.extend(todo)
    return "\n".join(out)


def _shorthand(raw):
    m = re.match(r"^m(\d+)(/.*)$", raw)
    if m:
        return "src/missions/m%s%s" % (m.group(1), m.group(2))
    head, sep, rest = raw.partition("/")
    if sep and head in SHORT:
        return SHORT[head] + "/" + rest
    return raw


class Resolver:
    """Maps the paths an AI writes to real files under ROOT."""

    def __init__(self, root):
        self.root = Path(root)
        self.real = self.root.resolve()
        self._index = None
        self.ambiguous = {}             # raw -> [rel, ...] for bare names found 2+ times

    def _rel(self, cand):
        """Real-case rel path of an existing file inside the project, else None."""
        try:
            if cand.is_file():
                rel = cand.resolve().relative_to(self.real).as_posix()
                if rel not in RESERVED:
                    return rel
        except (OSError, ValueError):   # outside the project (.., symlink) or a bad name
            pass
        return None

    def by_name(self):
        if self._index is None:
            idx = {}
            for base in (self.root / "src", self.root / "tools", self.root / "tests",
                         self.root / "docs"):
                if not base.is_dir():
                    continue
                for d, dirs, files in os.walk(base):
                    dirs[:] = [x for x in dirs if x not in ("__pycache__", ".git")]
                    for f in files:
                        idx.setdefault(f.lower(), []).append(Path(d) / f)
            self._index = idx
        return self._index

    def find(self, raw, prefix=""):
        """Return a path relative to ROOT (posix) or None."""
        raw = re.sub(r"^(?:\.?/)+", "", raw.strip().strip("`'\"").replace("\\", "/"))
        if not raw or re.match(r"^[A-Za-z]:/", raw):
            return None
        tries = [raw]
        if prefix:                       # a bare name under a listed folder
            tries.insert(0, prefix.rstrip("/") + "/" + raw)
        for t in list(tries):
            tries += [_shorthand(t)]
        for t in tries:
            for cand in (self.root / t, self.root / "src" / t):
                rel = self._rel(cand)
                if rel:
                    return rel
        hits = list(dict.fromkeys(filter(None, (self._rel(h) for h in
                                                self.by_name().get(Path(raw).name.lower(), [])))))
        if len(hits) == 1:
            return hits[0]
        parts = raw.split("/")           # an absolute or space-split path: try its tails
        for k in range(1, len(parts) - 1):
            tail = "/".join(parts[k:])
            for cand in (self.root / tail, self.root / "src" / tail):
                rel = self._rel(cand)
                if rel:
                    return rel
        if len(hits) > 1:
            self.ambiguous[raw] = hits
        return None


def _is_dir(root, rel):
    """True if rel names a folder of the project (also via the src/ shorthand)."""
    try:
        base = Path(root)
    except TypeError:
        return False
    for cand in (base / rel, base / "src" / rel, base / _shorthand(rel)):
        if cand.is_dir():
            return True
    return False


def parse_request(text, root):
    """-> (requests, missing). Request = {rel, desc, ranges}."""
    text = expand_braces(text.replace("\r\n", "\n").replace("\r", "\n"))
    res = Resolver(root)
    reqs, order, missing = {}, [], []
    listed_seq = {}
    whole = set()                               # listed on a bullet with no line range
    stack = []                                  # [(indent, dir prefix)]
    dirs, folders, used = {}, [], set()         # _is_dir cache; bare folder lines; prefixes hit
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        while stack and stack[-1][0] >= indent:
            stack.pop()
        body = BULLET_RE.sub("", line)
        # a folder bullet such as "  - src/missions/m1/" scopes the lines below it
        stripped = body.strip()
        head_tok = stripped.split()[0].strip("`'\"*") if stripped else ""
        hits = list(PATH_RE.finditer(body))
        line_dir = ""
        if head_tok and not PATH_RE.match(head_tok):
            probe = head_tok.replace("\\", "/").rstrip(".,;:")
            is_dir = probe.endswith("/")
            probe = probe.rstrip("/")
            if probe and probe not in dirs:
                dirs[probe] = is_dir or _is_dir(root, probe)
            if probe and (is_dir or dirs[probe]):
                stack.append((indent, probe))
                if not hits:                    # "- src/ui/" alone: must get files below it
                    if "/" in head_tok.replace("\\", "/"):
                        folders.append(probe)
                    continue
                line_dir = probe                # "- src/core/ state.py": files on this line
        if not hits:
            continue
        prefix = line_dir
        for ind, pre in ([] if prefix else reversed(stack)):
            if ind < indent:
                prefix = pre
                break
        listed = bool(BULLET_RE.match(line)) or bool(re.match(r"^\s*>", line))
        desc_parts = []
        seen_here = []
        for k, m in enumerate(hits):
            tok = m.group(1)
            before = body[max(0, m.start() - 200):m.start()]
            if re.search(r"://\S*$", before):        # a URL's tail is not a project path
                continue
            end = hits[k + 1].start() if k + 1 < len(hits) else len(body)
            rest = body[m.end():end]
            rm = RANGE_RE.match(rest)
            ranges = []
            if rm:
                a = int(rm.group(1)) if rm.group(1) else 1
                b = int(rm.group(2)) if rm.group(2) else None
                if b is None or b >= a:
                    ranges = [(a, b)]
                rest = rest[rm.end():]
            rel = res.find(tok, prefix)
            if not rel:
                norm = re.sub(r"^(?:\.?/)+", "", tok.replace("\\", "/"))
                if tok not in missing and norm not in RESERVED and "mN" not in tok:
                    missing.append(tok)
                continue
            if prefix:
                used.add(prefix)
            seen_here.append(rel)
            if rel not in reqs:
                reqs[rel] = {"rel": rel, "desc": "", "ranges": [], "listed": False}
                order.append(rel)
            if listed:
                reqs[rel]["listed"] = True
                listed_seq.setdefault(rel, len(listed_seq))
            if ranges:
                reqs[rel]["ranges"] += ranges
            elif listed:
                whole.add(rel)
            desc_parts.append(rest)
        tail = "".join(desc_parts) if seen_here else ""
        tail = tail.replace("`", " ").replace("*", " ")
        tail = re.sub(r"^[\s\-:\u2013\u2014\u2022|>)]+", "", tail).strip()
        if tail:
            # the description may wrap onto deeper-indented lines
            j = i
            extra = []
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    break
                nind = len(nxt) - len(nxt.lstrip())
                if nind <= indent or PATH_RE.search(nxt) or BULLET_RE.match(nxt):
                    break
                extra.append(nxt.strip())
                j += 1
            if extra:
                tail = (tail + " " + " ".join(extra)).strip()
                i = j
        tail = tidy_desc(tail)
        for rel in dict.fromkeys(seen_here):
            if tail:
                reqs[rel]["desc"] = tidy_desc(reqs[rel]["desc"] + " " + tail)
    for rel in whole:                           # a bullet asking for the file beats a range
        reqs[rel]["ranges"] = []
    listed = sorted(listed_seq, key=lambda r: listed_seq[r])
    rest = [r for r in order if r not in listed_seq]
    missing +=[f + "/ (folder: name its files)" for f in dict.fromkeys(folders) if f not in used]
    for i, tok in enumerate(missing):
        hits = res.ambiguous.get(re.sub(r"^(?:\.?/)+", "", tok.strip("`'\"").replace("\\", "/")))
        if hits:
            missing[i] = "%s (ambiguous: %s)" % (tok, ", ".join(hits[:3]) +
                                                ("" if len(hits) <= 3 else " +%d" % (len(hits) - 3)))
    return [reqs[r] for r in listed + rest], missing


# ------------------------------------------------------------- symbol slicing
class Sym:
    __slots__ = ("name", "lo", "hi", "owner", "kind")

    def __init__(self, name, lo, hi, owner, kind):
        self.name, self.lo, self.hi, self.owner, self.kind = name, lo, hi, owner, kind

    @property
    def base(self):
        return self.name.lstrip("_")

    @property
    def parts(self):
        return {p for p in self.base.lower().split("_") if p}


def _def_lo(node):
    deco = getattr(node, "decorator_list", None) or []
    return min([node.lineno] + [d.lineno for d in deco])


def collect_symbols(tree):
    syms = []

    def add_assign(node):
        names = []
        targets = getattr(node, "targets", None) or ([node.target] if getattr(node, "target", None) else [])
        for t in targets:
            if isinstance(t, ast.Name):
                names.append(t.id)
        for n in names:
            syms.append(Sym(n, node.lineno, node.end_lineno, None, "const"))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            syms.append(Sym(node.name, _def_lo(node), node.end_lineno, None, "def"))
        elif isinstance(node, ast.ClassDef):
            syms.append(Sym(node.name, _def_lo(node), node.end_lineno, None, "class"))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    syms.append(Sym(sub.name, _def_lo(sub), sub.end_lineno, node.name, "method"))
                elif isinstance(sub, (ast.Assign, ast.AnnAssign)):
                    add_assign(sub)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            add_assign(node)
    return syms


def prologue_end(tree, total):
    """1..N covering the docstring and the leading imports."""
    end = 1
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
        end = body[0].end_lineno
        body = body[1:]
    for node in body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            end = node.end_lineno
        else:
            break
    return min(max(end, 1), total, LEAD_LIMIT)


def _doc_end(cls):
    body = list(cls.body) if hasattr(cls, "body") else []
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
        return body[0].end_lineno
    return None


def relevant_by_body(syms, lines, words):
    """Functions whose own body talks about >= 2 of the things that were asked for.

    Names the AI guessed ("player pose", "weapon hold") rarely match this repo's
    helpers, so the body text is the second signal. A word used by nearly every
    symbol carries no information and is dropped.
    """
    topic = [w for w in words if len(w) >= 4 and w not in FILLER]
    if not topic:
        return []
    texts = {}
    for s in syms:
        texts[(s.name, s.lo)] = "\n".join(lines[s.lo - 1:s.hi]).lower()
    limit = max(5, int(len(syms) * 0.45))
    df = {}
    for w in topic:
        pat = re.compile(r"\b%s" % re.escape(w))
        df[w] = sum(1 for t in texts.values() if pat.search(t))
    good = [w for w in topic if 1 <= df[w] <= limit]
    if len(good) < 2:
        return []
    pats = [(w, re.compile(r"\b%s" % re.escape(w))) for w in good]
    out = []
    for s in syms:
        if s.kind == "class":
            continue
        body = texts[(s.name, s.lo)]
        if sum(1 for _, p in pats if p.search(body)) >= 2:
            out.append(s)
    return out


def pick_symbols(text, desc):
    """-> [(lo, hi, names), ...] by the names the request asked for, or (None, reason)."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None, "not parseable"
    syms = collect_symbols(tree)
    if not syms:
        return None, "no definitions"
    words = {w.lower() for w in ID_RE.findall(desc)}
    exact = set(ID_RE.findall(desc))
    dotted = {(a.lower(), b.lower()) for a, b in DOT_ID_RE.findall(desc)}
    picked = []
    for s in syms:
        hit = s.name in exact or s.base in exact or s.base.lower() in words
        if s.owner and (s.owner.lower(), s.base.lower()) in dotted:
            hit = True
        if len(s.parts) >= 2 and s.parts <= words:      # "player pose" -> _player_pose
            hit = True
        if hit:
            picked.append(s)
    by_part = {}
    for s in syms:
        for p in s.parts:
            by_part.setdefault(p, []).append(s)
    for word in words - exact - FILLER:
        if len(word) < 4:                               # a word naming at most RARE symbols
            continue                                    # is specific: "molotov", "pose"
        hits = by_part.get(word, [])
        if 1 <= len(hits) <= RARE:
            picked += hits
    lines = text.split("\n")                            # ast numbers lines by \n only,
    if lines and lines[-1] == "":                       # splitlines() also splits \f, \x1c..
        lines.pop()
    if len({(s.name, s.lo) for s in picked}) < 4:       # the names guessed were too few:
        picked += relevant_by_body(syms, lines, words)  # read what the bodies say
    if words & ACTOR_WORDS:                             # any draw3d's actor helpers, by name
        picked += [s for s in syms if s.name in ACTOR_NAMES]
    uniq = {}
    for s in picked:
        uniq.setdefault((s.name, s.lo), s)
    picked = [uniq[k] for k in sorted(uniq, key=lambda k: (k[1], k[0]))]
    if not picked:
        return None, "no names matched"
    total = len(lines)
    labels = [(1, prologue_end(tree, total), "prologue")]
    for s in picked:
        if s.kind == "class":
            span = s.hi - s.lo + 1
            labels.append((s.lo, s.hi if span <= 150 else min(s.hi, s.lo + 6), s.name))
        else:
            labels.append((s.lo, s.hi, s.name))
            if s.owner:                                  # the owner so a method has context
                owner = next((c for c in syms if c.kind == "class" and c.name == s.owner), None)
                if owner:
                    head_hi = _doc_end(owner) or owner.lo
                    labels.append((owner.lo, min(head_hi, max(owner.lo, s.lo - 1)),
                                   "class " + owner.name))
    spans = sorted((max(1, a), min(b, total)) for a, b, _ in labels if b and b >= a)
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1] + GAP + 1:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    covered = sum(b - a + 1 for a, b in merged)
    if covered > total * FULL_COVER:
        return None, "slices cover most of it"
    if covered < total * 0.05:                          # a sliver is a guess, not a slice
        return None, "too little matched"
    out = []
    for a, b in merged:
        names = []
        for la, lb, label in sorted(labels, key=lambda t: t[0]):
            if la >= a and lb <= b and label not in names:
                names.append(label)
        out.append((a, b, [] if names == ["prologue"] else names))
    return out, None


def file_text(path):
    try:
        raw = Path(path).read_bytes()
    except (OSError, MemoryError):
        return None
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    text = raw.decode(enc, errors="replace")
    # lone \r is a line break to ast; a NUL would end the Windows clipboard text early
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "�")


PREVIEW_CAP = 1_500_000   # chars shown in the window; Copy always copies the whole bundle


FULL_WORDS = re.compile(r"\b(?:full|whole|entire)\s+(?:file|source)\b", re.I)

# connectives that carry no slicing signal - they only make the table noisy
CONNECT = {"and", "also", "plus", "then", "please", "thanks", "too", "as", "well",
           "with", "for", "the", "a", "an"}
EDGE_JUNK = "|,;:.-+&*()`'\" "


def tidy_desc(text):
    """Trim leading/trailing connectives and stray separators from a description."""
    words = text.split()
    while words and (not words[0].strip(EDGE_JUNK)
                     or words[0].lower().strip(EDGE_JUNK) in CONNECT):
        words.pop(0)
    while words and (not words[-1].strip(EDGE_JUNK)
                     or words[-1].lower().strip(EDGE_JUNK) in CONNECT):
        words.pop()
    return " ".join(words)


def build_bundle(reqs, root, slice_big=True, threshold=SLICE_LINES):
    """-> (text, rows, missing). rows describe what went into the bundle."""
    out, rows, missing = [], [], []
    for req in reqs:
        full = Path(root) / req["rel"]
        text = file_text(full)
        if text is None:
            missing.append(req["rel"])
            continue
        lines = text.split("\n")
        if lines[-1] == "":                 # a final newline ends the last line, not a new one
            lines.pop()
        n = len(lines)
        mode, parts = "full", []
        if req["ranges"]:
            mode = "lines"
            for a, b in sorted(req["ranges"]):
                lo, hi = max(1, a), min(n, b or n)
                if lo > hi:
                    missing.append("%s:%d-%s (file has %d lines)" % (req["rel"], a, b or "", n))
                elif parts and lo <= parts[-1][1] + 1:     # repeated or overlapping range
                    parts[-1] = (parts[-1][0], max(hi, parts[-1][1]), [])
                else:
                    parts.append((lo, hi, []))
            if not parts:
                continue
        elif slice_big and n > threshold and not FULL_WORDS.search(req["desc"]):
            got, why = pick_symbols(text, req["desc"])
            if got:
                mode, parts = "slice", got
            else:
                mode, parts = "full", []
        for lo, hi, names in parts or [(1, n, [])]:
            chunk = lines[lo - 1:hi]
            tag = ""
            if (lo, hi) != (1, n):
                shown = ""
                if names:
                    shown = ": " + ", ".join(names[:4])
                    if len(names) > 4:
                        shown += " +%d more" % (len(names) - 4)
                tag = " (lines %d-%d of %d%s)" % (lo, hi, n, shown)
            out.append("--- START OF FILE %s%s ---\n%s\n--- END OF FILE %s ---\n"
                       % (req["rel"], tag, "\n".join(chunk), req["rel"]))
        rows.append({"rel": req["rel"], "mode": mode, "lines": n,
                     "sent": sum(hi - lo + 1 for lo, hi, _ in parts) if parts else n,
                     "parts": len(parts) or 1, "desc": req["desc"],
                     "names": [nm for _, _, nms in parts for nm in nms]})
    return "\n".join(out), rows, missing


# ---------------------------------------------------------------- clipboard
def copy_text(text):
    """Put text on the OS clipboard; survives the window closing on Windows."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            u32 = ctypes.WinDLL("user32", use_last_error=True)
            k32.GlobalAlloc.restype = wintypes.HGLOBAL
            k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
            k32.GlobalLock.restype = ctypes.c_void_p
            k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            u32.OpenClipboard.argtypes = [wintypes.HWND]
            u32.OpenClipboard.restype = wintypes.BOOL
            u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
            u32.SetClipboardData.restype = wintypes.HANDLE
            u32.CloseClipboard.restype = wintypes.BOOL
            data = text.encode("utf-16-le") + b"\x00\x00"
            blob = ctypes.create_string_buffer(data, len(data))
            for attempt in range(12):
                if u32.OpenClipboard(None):
                    break
                time.sleep(0.03)
            else:
                return False
            try:
                u32.EmptyClipboard()
                handle = k32.GlobalAlloc(0x0002, len(data))     # GMEM_MOVEABLE
                if not handle:
                    return False
                ptr = k32.GlobalLock(handle)
                ctypes.memmove(ptr, blob, len(data))
                k32.GlobalUnlock(handle)
                if not u32.SetClipboardData(13, handle):        # CF_UNICODETEXT
                    return False
            finally:
                u32.CloseClipboard()
            return True
        except Exception:
            pass
    try:                                     # non-Windows fallback
        import subprocess
        import shutil
        for cmd in (["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"]):
            if shutil.which(cmd[0]):
                subprocess.run(cmd, input=text.encode("utf-8"), check=True)
                return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------- settings
def load_settings():
    try:
        cfg = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return cfg if isinstance(cfg, dict) else {}


def save_settings(**kw):
    cur = load_settings()
    cur.update(kw)
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(cur, indent=1), encoding="utf-8")
    except OSError:
        pass


def windows_dark():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except (ImportError, OSError):
        return False


THEMES = {
    "light": dict(bg="#eef0f3", card="#ffffff", field="#fafbfc", line="#d8dce2", fg="#1f2328",
                  dim="#656d76", faint="#8c959f", acc="#2563eb", acc_hi="#1d4ed8",
                  acc_off="#a9c0f2", acc_off_fg="#f2f5fc", hover="#f3f4f6", sel="#e1ebfd",
                  thumb="#cdd2d9", thumb_hi="#aeb5bf", ok="#116329", warn="#9a6700",
                  red="#cf222e", head="#f6f7f9"),
    "dark": dict(bg="#16181d", card="#1e2128", field="#1a1d23", line="#2e333d", fg="#e6e8ec",
                 dim="#9aa2ae", faint="#6b7280", acc="#3b82f6", acc_hi="#2f6fe0",
                 acc_off="#24395f", acc_off_fg="#7b8bab", hover="#282c35", sel="#233350",
                 thumb="#3a404b", thumb_hi="#4d5462", ok="#7ee2a0", warn="#e3b341",
                 red="#f47067", head="#23262e"),
}


# ---------------------------------------------------------------- GUI
def gui(root=None, text=None, theme=None, shot=None, shot_theme=False):
    import threading
    import tkinter as tk
    import traceback
    from tkinter import filedialog, messagebox, ttk

    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    cfg = load_settings()
    saved = cfg.get("root")
    root = Path(root or (saved if isinstance(saved, str) else None) or ROOT)
    theme = theme or cfg.get("theme")
    if theme not in THEMES:                      # a hand-edited or stale settings file
        theme = "dark" if windows_dark() else "light"
    P = THEMES[theme]
    BG, CARD, FIELD, LINE, FG, DIM, ACC = (P[k] for k in
                                           ("bg", "card", "field", "line", "fg", "dim", "acc"))

    w = tk.Tk()
    w.withdraw()
    w.title(APP_NAME)
    px = w.winfo_fpixels("1i") / 96.0

    def S(v):
        return int(round(v * px))

    w.geometry("%dx%d" % (S(1240), S(820)))
    w.minsize(S(900), S(560))
    w.configure(bg=BG)
    ico = Path(getattr(sys, "_MEIPASS", HERE)) / "ai_bundle.ico"
    if ico.is_file():
        try:
            w.iconbitmap(str(ico))
        except tk.TclError:
            pass
    w.report_callback_exception = lambda *a: messagebox.showerror(
        APP_NAME, "Something went wrong:\n\n" + "".join(traceback.format_exception(*a))[-1200:])

    base, bold, mono = ("Segoe UI", 10), ("Segoe UI Semibold", 10), ("Consolas", 10)
    st = ttk.Style(w)
    st.theme_use("clam")
    st.configure(".", background=BG, foreground=FG, font=base, bordercolor=LINE,
                 lightcolor=BG, darkcolor=BG, focuscolor=BG)
    st.configure("Card.TFrame", background=CARD)
    st.configure("Card.TLabel", background=CARD)
    st.configure("Title.TLabel", font=("Segoe UI Semibold", 16))
    st.configure("Sub.TLabel", foreground=DIM)
    st.configure("Dim.TLabel", foreground=DIM)
    st.configure("Ok.TLabel", foreground=P["ok"])
    st.configure("Warn.TLabel", foreground=P["warn"])
    st.configure("TButton", background=CARD, foreground=FG, bordercolor=LINE, lightcolor=CARD,
                 darkcolor=CARD, padding=(S(12), S(5)))
    st.map("TButton", background=[("active", P["hover"])], lightcolor=[("active", P["hover"])],
           darkcolor=[("active", P["hover"])])
    st.configure("Link.TButton", background=BG, foreground=ACC, bordercolor=BG, lightcolor=BG,
                 darkcolor=BG, padding=(S(4), S(2)))
    st.map("Link.TButton", background=[("active", BG)], lightcolor=[("active", BG)],
           foreground=[("active", P["acc_hi"])])
    st.configure("Accent.TButton", background=ACC, foreground="white", bordercolor=ACC,
                 lightcolor=ACC, darkcolor=ACC, padding=(S(22), S(7)), font=bold)
    st.map("Accent.TButton", background=[("active", P["acc_hi"])],
           lightcolor=[("active", P["acc_hi"])], darkcolor=[("active", P["acc_hi"])])
    for orient in ("Vertical", "Horizontal"):
        st.layout(orient + ".TScrollbar", [(orient + ".Scrollbar.trough", {
            "sticky": "nswe", "children": [(orient + ".Scrollbar.thumb",
                                            {"expand": "1", "sticky": "nswe"})]})])
        st.configure(orient + ".TScrollbar", troughcolor=FIELD, background=P["thumb"],
                     bordercolor=FIELD, lightcolor=P["thumb"], darkcolor=P["thumb"], arrowsize=S(9))
        st.map(orient + ".TScrollbar", background=[("active", P["thumb_hi"])])
    st.configure("TCheckbutton", background=BG, foreground=DIM)
    st.map("TCheckbutton", background=[("active", BG)], foreground=[("active", FG)])
    st.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=FG,
                 rowheight=S(24), borderwidth=0)
    st.map("Treeview", background=[("selected", P["sel"])], foreground=[("selected", FG)])
    st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    st.configure("Treeview.Heading", background=P["head"], foreground=DIM, borderwidth=0,
                 font=("Segoe UI Semibold", 9))
    st.map("Treeview.Heading", background=[("active", P["head"])])

    state = {"bundle": "", "rows": [], "missing": [], "theme": theme, "root": Path(root),
             "restart": None, "draft": "", "built_text": None, "shot_id": None}

    # ---------------------------------------------------------------- header
    head = ttk.Frame(w, padding=(S(20), S(14), S(20), S(6)))
    head.pack(fill="x")
    ttk.Label(head, text=APP_NAME, style="Title.TLabel").pack(side="left")
    ttk.Label(head, text="  paste the AI's file list -> files on the clipboard",
              style="Sub.TLabel").pack(side="left", pady=(S(4), 0))
    theme_btn = ttk.Button(head, text="Light mode" if theme == "dark" else "Dark mode",
                           style="Link.TButton")
    theme_btn.pack(side="right")
    ttk.Label(head, text="|", style="Sub.TLabel").pack(side="right", padx=S(6))
    root_btn = ttk.Button(head, text="Change folder", style="Link.TButton")
    root_btn.pack(side="right")
    root_lbl = ttk.Label(head, style="Sub.TLabel")
    root_lbl.pack(side="right", padx=(0, S(4)))

    def show_root():
        r = str(state["root"])
        root_lbl.configure(text=(r[:58] + "...") if len(r) > 61 else r, foreground=DIM)

    show_root()

    # ---------------------------------------------------------------- footer
    foot = ttk.Frame(w, padding=(S(20), S(10), S(20), S(16)))
    foot.pack(side="bottom", fill="x")
    copy_btn = ttk.Button(foot, text="Copy bundle", style="Accent.TButton")
    copy_btn.pack(side="right")
    save_btn = ttk.Button(foot, text="Save .txt")
    save_btn.pack(side="right", padx=S(10))
    status = ttk.Label(foot, style="Dim.TLabel")
    status.pack(side="left")
    warn_lbl = ttk.Label(foot, style="Warn.TLabel")
    warn_lbl.pack(side="right", padx=(0, S(16)))

    opts = ttk.Frame(w, padding=(S(20), 0, S(20), S(8)))
    opts.pack(fill="x")
    slice_var = tk.BooleanVar(value=bool(cfg.get("slice", True)))
    auto_var = tk.BooleanVar(value=bool(cfg.get("auto", True)))
    slice_chk = ttk.Checkbutton(opts, text="Slice files over %d lines by the names it asks for"
                                % SLICE_LINES, variable=slice_var)
    slice_chk.pack(side="left")
    auto_chk = ttk.Checkbutton(opts, text="Copy as soon as I paste", variable=auto_var)
    auto_chk.pack(side="left", padx=(S(18), 0))
    example_btn = ttk.Button(opts, text="Example", style="Link.TButton")
    example_btn.pack(side="right")
    load_btn = ttk.Button(opts, text="Load message .txt", style="Link.TButton")
    load_btn.pack(side="right", padx=(0, S(8)))

    # ---------------------------------------------------------------- panes
    pw = ttk.Panedwindow(w, orient="vertical")
    pw.pack(fill="both", expand=True, padx=S(20), pady=(0, S(4)))

    top = ttk.Panedwindow(pw, orient="horizontal")
    pw.add(top, weight=3)

    left = ttk.Frame(top, style="Card.TFrame", padding=S(1))
    right = ttk.Frame(top, style="Card.TFrame", padding=S(1))
    top.add(left, weight=4)
    top.add(right, weight=6)

    ttk.Label(left, text="  The request", style="Card.TLabel").pack(anchor="w", padx=S(8), pady=(S(6), 0))
    msg = tk.Text(left, bg=FIELD, fg=FG, insertbackground=FG, relief="flat", wrap="word",
                  font=mono, padx=S(10), pady=S(8), undo=True, selectbackground=P["sel"],
                  selectforeground=FG, highlightthickness=0)
    msg.pack(fill="both", expand=True, padx=S(6), pady=S(6))
    sb = ttk.Scrollbar(left, orient="vertical", command=msg.yview)
    sb.place(relx=1.0, rely=0.06, relheight=0.92, anchor="ne")
    msg.configure(yscrollcommand=sb.set)

    ttk.Label(right, text="  What goes on the clipboard", style="Card.TLabel").pack(
        anchor="w", padx=S(8), pady=(S(6), 0))
    tree = ttk.Treeview(right, columns=("file", "mode", "lines"), show="headings", height=7)
    tree.heading("file", text="file")
    tree.heading("mode", text="what")
    tree.heading("lines", text="lines")
    tree.column("file", width=S(330), anchor="w", stretch=True)
    tree.column("mode", width=S(150), anchor="w", stretch=False)
    tree.column("lines", width=S(86), anchor="e", stretch=False)
    tree.pack(fill="x", padx=S(6), pady=(S(4), S(2)))
    prev_frame = ttk.Frame(right, style="Card.TFrame")
    prev_frame.pack(fill="both", expand=True, padx=S(6), pady=(0, S(6)))
    preview = tk.Text(prev_frame, bg=FIELD, fg=P["dim"], relief="flat", wrap="none",
                      font=("Consolas", 10), padx=S(10), pady=S(8), highlightthickness=0,
                      selectbackground=P["sel"], selectforeground=FG)
    preview.pack(side="left", fill="both", expand=True)
    pv_sb = ttk.Scrollbar(prev_frame, orient="vertical", command=preview.yview)
    pv_sb.pack(side="right", fill="y")
    preview.configure(yscrollcommand=pv_sb.set)
    px_sb = ttk.Scrollbar(right, orient="horizontal", command=preview.xview)
    px_sb.pack(fill="x", padx=S(6), pady=(0, S(6)))
    preview.configure(xscrollcommand=px_sb.set)
    preview.tag_configure("head", foreground=ACC, font=("Consolas", 10, "bold"))
    preview.tag_configure("end", foreground=P["faint"])

    # ---------------------------------------------------------------- logic
    jobs = {"gen": 0, "poll": None}

    def build(copy=False, then=None):
        """Parse and bundle on a worker thread; only this (Tk) thread touches widgets."""
        text = msg.get("1.0", "end-1c")
        state["built_text"] = text
        jobs["gen"] += 1
        gen, root_dir, slice_big = jobs["gen"], state["root"], slice_var.get()
        box = {}

        def work():                                  # no Tk calls in here
            try:
                reqs, missing = parse_request(text, root_dir)
                box["res"] = (reqs, missing) + build_bundle(reqs, root_dir, slice_big=slice_big)
            except Exception:
                box["err"] = traceback.format_exc()

        th = threading.Thread(target=work, daemon=True)
        th.start()
        w.configure(cursor="watch")

        def poll():
            jobs["poll"] = None
            if gen != jobs["gen"]:
                return                               # a newer build replaced this one
            if th.is_alive():
                jobs["poll"] = w.after(30, poll)
                return
            w.configure(cursor="")
            if "err" in box:                         # shown by report_callback_exception
                raise RuntimeError(box["err"])
            bundle = _build(copy, *box["res"])
            if then:
                then(bundle)

        poll()

    def _build(copy, reqs, missing, bundle, rows, gone):
        state["bundle"], state["rows"], state["missing"] = bundle, rows, missing + gone
        tree.delete(*tree.get_children())
        for r in rows:
            if r["mode"] == "full":
                what = "whole file"
            elif r["mode"] == "lines":
                what = "%d line range%s" % (r["parts"], "" if r["parts"] == 1 else "s")
            else:
                what = "%d slice%s" % (r["parts"], "" if r["parts"] == 1 else "s")
            tree.insert("", "end", values=(r["rel"], what, "%d/%d" % (r["sent"], r["lines"])))
        preview.configure(state="normal")
        preview.delete("1.0", "end")
        shown = bundle
        if len(bundle) > PREVIEW_CAP:
            cut = bundle.rfind("\n--- START OF FILE", 0, PREVIEW_CAP)
            shown = bundle[:cut if cut > 0 else PREVIEW_CAP]
            shown += ("\n\n... preview stops here: the bundle is %d characters. "
                      "Copy takes all of it. ..." % len(bundle))
        preview.insert("1.0", shown)
        # colour the file headers so the bundle's structure reads at a glance
        pos = "1.0"
        while True:
            pos = preview.search("--- START OF FILE", pos, stopindex="end", regexp=False)
            if not pos:
                break
            preview.tag_add("head", pos, "%s lineend" % pos)
            pos = "%s +1 line" % pos
        pos = "1.0"
        while True:
            pos = preview.search("--- END OF FILE", pos, stopindex="end", regexp=False)
            if not pos:
                break
            preview.tag_add("end", pos, "%s lineend" % pos)
            pos = "%s +1 line" % pos
        preview.configure(state="disabled")
        total = sum(r["sent"] for r in rows)
        sliced = sum(1 for r in rows if r["mode"] == "slice")
        if not reqs:
            status.configure(text="No file paths found in the message yet.", style="Dim.TLabel")
        else:
            status.configure(text="%d file%s - %d lines - %d sliced" %
                             (len(rows), "" if len(rows) == 1 else "s", total, sliced),
                             style="Ok.TLabel")
        bad = state["missing"]
        if bad:
            uniq = list(dict.fromkeys(bad))
            warn_lbl.configure(text="not found: " + ", ".join(uniq[:3]) +
                               ("" if len(uniq) <= 3 else " (+%d)" % (len(uniq) - 3)))
        else:
            warn_lbl.configure(text="")
        if copy:
            if not bundle:
                warn_lbl.configure(text="nothing to copy")
            elif copy_text(bundle):
                status.configure(text="Copied %d file%s - %d lines" %
                                 (len(rows), "" if len(rows) == 1 else "s", total),
                                 style="Ok.TLabel")
                w.after(1600, lambda: status.configure(style="Dim.TLabel"))
            else:
                warn_lbl.configure(text="clipboard busy - press Copy again")
        return bundle

    timer = {"id": None}

    def later():
        if timer["id"]:
            w.after_cancel(timer["id"])

        def run():
            timer["id"] = None
            if msg.get("1.0", "end-1c") != state["built_text"]:
                build()                  # re-parse only when the text really changed
        timer["id"] = w.after(120, run)

    def on_paste(_ev=None):
        w.after(30, lambda: auto_var.get() and build(copy=True))
        return None

    def jump(_ev=None):
        sel = tree.selection()
        if not sel or not state["bundle"]:
            return
        rel = tree.item(sel[0], "values")[0]
        idx = preview.search("--- START OF FILE %s" % rel, "1.0", stopindex="end")
        if idx:
            preview.see(idx)

    def copy_now():
        build(copy=True)

    def save_txt():
        def ask(text):
            if not text:
                return
            path = filedialog.asksaveasfilename(defaultextension=".txt",
                                                filetypes=[("Text", "*.txt")], title="Save bundle")
            if path:
                Path(path).write_text(text, encoding="utf-8")
                status.configure(text="Saved " + Path(path).name, style="Ok.TLabel")
        build(then=ask)

    def stop_jobs():
        """Cancel pending after() work so a destroyed window never runs it."""
        for jid in (timer.get("id"), state.get("shot_id"), jobs.get("poll")):
            if jid:
                try:
                    w.after_cancel(jid)
                except tk.TclError:
                    pass
        timer["id"] = state["shot_id"] = jobs["poll"] = None
        jobs["gen"] += 1                 # a worker still running is ignored when it lands

    def do_theme():
        nxt = "light" if state["theme"] == "dark" else "dark"
        state["draft"] = msg.get("1.0", "end-1c")[:400000]
        save_settings(theme=nxt, **{"root": str(state["root"]), "slice": slice_var.get(),
                                    "auto": auto_var.get(), "draft": state["draft"]})
        state["restart"] = nxt
        stop_jobs()
        w.destroy()

    def change_root():
        d = filedialog.askdirectory(initialdir=str(state["root"]), title="Project folder")
        if d:
            state["root"] = Path(d)
            show_root()
            later()

    def load_file():
        p = filedialog.askopenfilename(filetypes=[("Text", "*.txt *.md"), ("All", "*.*")],
                                       title="Load the AI's message")
        if p:
            msg.delete("1.0", "end")
            msg.insert("1.0", Path(p).read_text(encoding="utf-8", errors="replace"))
            build()

    def example():
        msg.delete("1.0", "end")
        msg.insert("1.0", SAMPLE)
        build(copy=False)

    copy_btn.configure(command=copy_now)
    save_btn.configure(command=save_txt)
    theme_btn.configure(command=do_theme)
    root_btn.configure(command=change_root)
    load_btn.configure(command=load_file)
    example_btn.configure(command=example)
    msg.bind("<<Paste>>", on_paste)
    msg.bind("<KeyRelease>", lambda ev: later())
    msg.bind("<Control-Return>", lambda ev: (copy_now(), "break")[1])
    tree.bind("<<TreeviewSelect>>", jump)
    for chk in (slice_chk, auto_chk):
        chk.configure(command=lambda: (later(), save_settings(
            theme=state["theme"], **{"root": str(state["root"]),
                                     "slice": slice_var.get(), "auto": auto_var.get()})))

    def on_close():
        save_settings(theme=state["theme"], **{"root": str(state["root"]),
                                              "slice": slice_var.get(),
                                              "auto": auto_var.get(),
                                              "draft": msg.get("1.0", "end-1c")[:400000]})
        stop_jobs()
        w.destroy()

    w.protocol("WM_DELETE_WINDOW", on_close)
    msg.insert("1.0", text if text is not None else str(cfg.get("draft") or ""))
    w.deiconify()
    msg.focus_set()
    build()
    if shot:
        def grab():
            if jobs["poll"]:                         # wait for the first build to land
                state["shot_id"] = w.after(100, grab)
                return
            w.update_idletasks()
            w.lift()
            w.attributes("-topmost", True)
            w.update()
            try:
                from PIL import ImageGrab
                x, y = w.winfo_rootx(), w.winfo_rooty()
                box = (x, y, x + w.winfo_width(), y + w.winfo_height())
                ImageGrab.grab(bbox=box, all_screens=True).save(shot)
                print("shot:", shot, box)
            except Exception as exc:                 # pillow missing or no desktop
                print("shot failed:", exc)
            stop_jobs()
            w.destroy()
        if shot_theme:                                # exercise the theme switch first
            w.after(250, theme_btn.invoke)
        state["shot_id"] = w.after(600 if shot_theme else 250, grab)
        w.mainloop()
        if state.get("restart"):
            return gui(root=state["root"], text=state["draft"], theme=state["restart"],
                       shot=shot, shot_theme=False)
        return None
    w.mainloop()
    if state.get("restart"):       # theme switch: rebuild the window, keep the paste
        return gui(root=state["root"], text=state["draft"], theme=state["restart"])
    return None


# ---------------------------------------------------------------- CLI
def report(rows, missing):
    out = []
    for r in rows:
        what = {"full": "whole file", "lines": "line range", "slice": "slice"}[r["mode"]]
        out.append("  %-52s %-12s %5d/%-5d %s" % (r["rel"], what, r["sent"], r["lines"],
                                                  "" if r["mode"] == "full" else
                                                  str(r["parts"]) + " part(s)"))
    for m in dict.fromkeys(missing):
        out.append("  MISSING  " + m)
    return "\n".join(out)


def selftest():
    reqs, missing = parse_request(SAMPLE, ROOT)
    want = {r["rel"] for r in reqs}
    expect = {"src/core/state.py", "src/entities/player.py", "src/entities/weapons.py",
              "src/game/topdown3d.py", "src/missions/m6/yard3d.py",
              "src/missions/m7/raid3d.py", "src/missions/m8/revenge/trap3d.py",
              "src/missions/m8/revenge/trap_hud.py", "src/ui/arena_view3d.py",
              "src/missions/m1/draw3d.py", "src/missions/m2/draw3d.py",
              "src/missions/m3/draw3d.py", "src/missions/m4/draw3d.py",
              "src/missions/m5/draw3d.py", "src/missions/m6/draw3d.py"}
    bundle, rows, gone = build_bundle(reqs, ROOT)
    ok = want == expect and not missing and not gone and len(rows) == 15 and all(
        ("--- START OF FILE %s" % r["rel"]) in bundle for r in rows) and bundle.endswith("---\n")
    print("AI BUNDLE SELFTEST:", "OK" if ok else "FAIL")
    print(report(rows, missing + gone))
    print("  bundle: %d bytes, %d blocks" % (len(bundle), bundle.count("--- START OF FILE")))
    if want != expect:
        print("  extra:", sorted(want - expect), "missing:", sorted(expect - want))
    return 0 if ok else 1


def main(argv):
    global ROOT
    text = None
    if "--selftest" in argv:
        return selftest()
    try:
        if "--root" in argv:
            ROOT = Path(argv[argv.index("--root") + 1]).resolve()
        msg_file = argv[argv.index("--check") + 1] if "--check" in argv else (
            argv[argv.index("--message-file") + 1] if "--message-file" in argv else None)
        if msg_file:
            text = Path(msg_file).read_text(encoding="utf-8", errors="replace")
    except (IndexError, OSError) as exc:
        print("ai_bundle_app: bad arguments or unreadable file: %s" % (exc or "missing value"),
              file=sys.stderr)
        return 2
    if msg_file:
        reqs, missing = parse_request(text, ROOT)
        bundle, rows, gone = build_bundle(reqs, ROOT)
        if "--out" in argv:
            try:
                Path(argv[argv.index("--out") + 1]).write_text(bundle, encoding="utf-8")
            except (IndexError, OSError) as exc:
                print("ai_bundle_app: cannot write --out: %s" % exc, file=sys.stderr)
                return 2
        if "--clip" in argv:
            print("clipboard:", "ok" if copy_text(bundle) else "failed")
        if "--check" in argv:
            print(report(rows, missing + gone))
            print("%d files, %d lines, %d bytes" % (len(rows), sum(r["sent"] for r in rows),
                                                    len(bundle)))
            if missing or gone:
                return 1
            return 0
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(bundle)
        return 0
    if "--shot" in argv:
        out = argv[argv.index("--shot") + 1]
        draft = Path(argv[argv.index("--message") + 1]).read_text(encoding="utf-8") \
            if "--message" in argv else None
        gui(text=draft, shot=out, shot_theme="--shot-theme" in argv,
            theme=(argv[argv.index("--theme") + 1] if "--theme" in argv else None))
        return 0
    gui()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
