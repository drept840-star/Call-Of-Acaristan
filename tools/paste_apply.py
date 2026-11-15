"""Paste Apply - apply an AI-written change set from a paste, no agent needed.

    python tools/paste_apply.py [--root DIR]        GUI
    python tools/paste_apply.py --check FILE        parse + dry run, print report
    python tools/paste_apply.py --apply FILE        apply what the GUI would tick by default
    python tools/paste_apply.py --undo              restore the last apply from its backup
    python tools/paste_apply.py --selftest
    python tools/paste_apply.py --shot OUT.png [PASTE [ROW]]   screenshot the GUI (needs Pillow)

Understands, anywhere in the paste (fenced or not):
  - unified diffs (--- a/x / +++ b/x / @@ hunks); line numbers are only hints,
    hunks are found by their context, blank context lines that lost their
    leading space still match, and context can drift by whitespace/indent
  - "New file: path" / "Full file: path" / "Delete file: path" headers,
    with the body in a ``` fence or unfenced up to the next section header
  - a ``` fence right under a line naming a path (whole-file write)
  - <<<<<<< SEARCH / ======= / >>>>>>> REPLACE blocks under a path line
  - header-less diffs under a path line ("Patch: src/x.py" then lines of
    " ", "+", "-"); "..." or blank lines between parts split them into hunks
  - a Python class/def under a heading that says "before X" / "after X"
    (fenced or not) is inserted there
Later blocks win: when a block only applies once an earlier block on the same file
is unticked, the earlier one is unticked (AIs restate a block, corrected, further down).
Safety: a diff applies all its hunks or none; anything that would break Python/JSON
syntax, shrink a file by half, or write an AI placeholder ("... rest unchanged")
is held back for review; every apply backs the files up to %APPDATA%/PasteApply.
"""
import codecs
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import warnings

FROZEN = getattr(sys, "frozen", False)
HERE = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))


def project_of(d):  # nearest folder above d holding .git, so the exe can live in a subfolder like apps/
    p = d
    while not os.path.isdir(os.path.join(p, ".git")):
        if os.path.dirname(p) == p:
            return d
        p = os.path.dirname(p)
    return p


DEFAULT_ROOT = project_of(HERE)
DATA = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "PasteApply")
BACKUPS = os.path.join(DATA, "backups")
SETTINGS = os.path.join(DATA, "settings.json")

KW = (r"new file|(?:create|add)[ds]? (?:a )?(?:new )?file|full file|whole file|complete file|"
      r"replace(?:ment)? file|rewrite|overwrite|(?:delete|remove)d? file")
HEADER = re.compile(r"^[\s\d.)#*>_-]*(?:%s)\b" % KW, re.I)  # the keyword must open the line, prose doesn't count
DELETE = re.compile(r"\b(?:delete|remove)d? file\b", re.I)
PATH = re.compile(r"`([^`\s]+\.\w+)`|((?:[\w.\-]+/)+[\w.\-]+\.\w+|\b[\w\-]+\.(?:py|json|md|txt|js|ts|toml|yaml|yml|"
                  r"cfg|ini|bat|cmd|ps1|sh|glsl|vert|frag|html|css)\b)")
SECTION = re.compile(r"\b(patch|diff|update|modif|edit|change)", re.I)
PLACEHOLDER = re.compile(
    r"^\s*(?:#|//|/\*|<!--|--|\*)?\s*(?:\.\.\.|…)\s*(?:\*/|-->)?\s*$|"
    r"\b(?:rest of (?:the )?(?:file|code|module|function|class)|(?:remains?|stays?|left) unchanged|"
    r"unchanged (?:code|lines|below|above)|existing code (?:here|below|above|unchanged)|"
    r"same as before|code omitted|omitted for brevity)\b", re.I)
SHELL = {"bash", "sh", "shell", "console", "powershell", "pwsh", "ps", "ps1", "cmd", "bat", "zsh", "text", "output"}
HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
CODE = re.compile(r"(?:async\s+def|def|class)\s+\w+")
MODSTART = re.compile(r"(?:\"\"\"|'''|#!|from\s+[\w.]+\s+import\b|import\s+\w)")
WHOLE = re.compile(r"replace|drop-in|full|whole|complete|rewrit|overwrit|new file", re.I)
# shell lines worth running after an apply; only python/pytest, and only these are ticked by default
CMD = re.compile(r"^(?:\$|>|PS[^>]*>)?\s*((?:python3?|py)\s+(?:-\S+\s+)*(?:[\w./\\-]+\.py\b|-m\s+\w)[^`]*|pytest\b[^`]*)$")
AUTO = re.compile(r"^(?:python3?|py)\s+(?:-[IuBO]+\s+)*(?:(?:tools|tests)[/\\]\S+\.py\b|"
                  r"-m\s+(?:compileall|py_compile|pytest|unittest)\b)|^pytest\b")
IMAGES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
NO_SCAN = {".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist"}
GAP = ("...", "…")
NORMS = (("exact", lambda s: s), ("ws", str.rstrip), ("indent", lambda s: " ".join(s.split())))
GOOD = ("ok", "new", "replace", "delete", "fuzzy", "run")  # ticked by default


class Op:
    def __init__(self, kind, path, data, label, explicit=False):
        self.kind, self.path, self.data, self.label, self.explicit = kind, path, data, label.strip(), explicit
        self.enabled, self.status, self.note, self.before, self.after = True, "", "", None, None
        self.superseded, self.tried = None, False


# ---------------------------------------------------------------- parsing

def header_path(line):
    m = PATH.search(line)
    if not m:
        return None
    p = (m.group(1) or m.group(2)).strip("*_:,;")
    return p if not p.startswith(("http", "www.")) else None


def path_only(line):
    """A line that is just a path (with markdown dressing) -> that path."""
    s = line.strip().strip("*#>`: ")
    for pre in ("File:", "file:", "Path:", "path:"):
        if s.startswith(pre):
            s = s[len(pre):].strip(" `*")
    return s if s and " " not in s and PATH.fullmatch(s) else None


def is_diff_start(L, i):
    return L[i].startswith("--- ") and i + 1 < len(L) and L[i + 1].startswith("+++ ")


def is_boundary(L, k):
    s = L[k]
    if is_diff_start(L, k) or s.startswith("diff --git") or s.strip().startswith("<<<<<<< SEARCH"):
        return True
    if re.match(r"\d{1,2}[a-z]?[.)]\s+\S", s) and (HEADER.match(s) or SECTION.search(s)):
        return True
    if re.match(r"#{2,6}\s", s):
        return True
    return bool(HEADER.match(s) and header_path(s) and not re.match(r"\s|#[^#]", s))


def parse_diff(L, i):
    def clean(p):
        p = p[4:].split("\t")[0].strip()
        return p[2:] if p[:2] in ("a/", "b/") else p
    old, new = clean(L[i]), clean(L[i + 1])
    i += 2
    hunks = []
    while i < len(L) and L[i].startswith("@@"):
        m = HUNK.match(L[i])
        a = int(m.group(1)) if m else None
        want = (int(m.group(2) or 1), int(m.group(4) or 1)) if m else None
        i += 1
        body, idx, o, n, cut = [], [], 0, 0, None
        while i < len(L):
            x = L[i]
            if x.startswith("@@") or x.startswith("diff --git") or is_diff_start(L, i):
                break
            if x.startswith("\\"):
                i += 1
                continue
            if x and x[0] not in " +-":
                break
            body.append(x)
            idx.append(i)
            o += x[:1] != "+"
            n += x[:1] != "-"
            if want and cut is None and (o, n) == want:
                cut = len(body)
            i += 1
        nxt = i < len(L) and (L[i].startswith(("@@", "diff --git")) or is_diff_start(L, i))
        # header counts end the hunk before trailing prose; not when another hunk follows (AI counts are often off)
        if cut is not None and not nxt and (o > want[0] or n > want[1]):
            i, body = idx[cut], body[:cut]
        while body and body[-1] == "":
            body.pop()
        hunks.append((a, body))
    if new == "/dev/null":
        return Op("delete", old, None, "diff: delete " + old, True), i
    if old == "/dev/null":
        lines = [x[1:] for _, b in hunks for x in b if x.startswith("+")]
        return Op("write", new, lines, "diff: new file " + new, True), i
    return Op("diff", new, hunks, "diff: " + new), i


def bare_end(L, i):
    """End of a header-less diff starting at i (needs a context line and a +/- line), or None."""
    if i and L[i - 1].strip() and not L[i - 1].strip().startswith("```"):
        return None  # starts mid-paragraph: a wrapped prose line like "--flag does X"
    k, ctx, add = i, 0, 0
    while k < len(L):
        x = L[k]
        if x.strip() and x.strip() not in GAP:
            if x[0] not in " +-" or is_diff_start(L, k) or x.startswith("diff --git"):
                break
            ctx += x[0] == " "
            add += x[0] == "+"
        k += 1
    while k > i and (not L[k - 1].strip() or L[k - 1].strip() in GAP):
        k -= 1
    return k if ctx and add else None  # needs a '+': a "- bullet" list with indented wraps is not a diff


def bare_hunks(lines):
    """Split a header-less diff into hunks at '...' lines; blank lines stay as blank context."""
    hunks, cur = [], []
    for x in lines + ["..."]:
        if x.strip() in GAP:
            while cur and not cur[-1].strip():
                cur.pop()
            if any(y[:1] in "+-" for y in cur):
                hunks.append((None, cur))
            cur = []
        elif cur or x.strip():
            cur.append(x if x.strip() else "")
    return hunks


def module_end(L, i):
    """End of an unfenced whole Python module starting at i: the longest stretch that compiles
    and has a top-level def/class, cut where a column-0 line follows a blank (prose after it)."""
    lim = next((k for k in range(i + 1, len(L)) if is_boundary(L, k) or L[k].strip().startswith("```")), len(L))
    cuts = [lim] + [k for k in range(lim - 1, i + 1, -1) if L[k][:1].strip() and not L[k - 1].strip()]
    for c in cuts:
        body = L[i:c]
        if not any(CODE.match(x) for x in body):
            return None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                compile("\n".join(body), "<paste>", "exec")
            return c
        except (SyntaxError, ValueError):
            continue
    return None


def heading(L, i):
    h = i - 1
    while h >= 0 and not L[h].strip():
        h -= 1
    return L[h] if h >= 0 else ""


def insert_op(path, body, head):
    """A class/def block placed by its heading: 'before X' wins over 'after X'."""
    spots = re.findall(r"\b(before|after)\s+[`*'\"]*([A-Za-z_]\w*)", head, re.I)
    spot = next((s for s in spots if s[0].lower() == "before"), spots[0] if spots else (None, None))
    return Op("insert", path, (body, spot[0] and spot[0].lower(), spot[1]), head or "code block")


def parse(text):
    L = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ops, closers, last_path, last_line, i = [], set(), None, "", 0
    seen = set()

    def command(line):
        m = CMD.match(line.strip())
        if m and m.group(1).strip() not in seen:
            seen.add(m.group(1).strip())
            ops.append(Op("run", None, m.group(1).strip(), m.group(1).strip()))
        return bool(m)

    while i < len(L):
        s, st = L[i], L[i].strip()
        if i in closers:
            i += 1
            continue
        if st.startswith("<<<<<<< SEARCH"):
            j = i + 1
            while j < len(L) and not L[j].strip().startswith("======="):
                j += 1
            k = j + 1
            while k < len(L) and not L[k].strip().startswith(">>>>>>> REPLACE"):
                k += 1
            ops.append(Op("replace", last_path, (L[i + 1:j], L[j + 1:k]), "search/replace " + (last_path or "?")))
            i = k + 1
            continue
        if is_diff_start(L, i):
            op, i = parse_diff(L, i)
            ops.append(op)
            continue
        if st.startswith("```"):
            fence = st[:len(st) - len(st.lstrip("`"))]
            info = st[len(fence):].strip()
            j = i + 1
            while j < len(L) and not L[j].strip().startswith(fence):
                j += 1
            body = L[i + 1:j]
            if any(x.startswith("+++ ") for x in body) or any(x.strip().startswith("<<<<<<< SEARCH") for x in body) \
                    or (j > i + 1 and bare_end(L, i + 1)):
                closers.add(j)  # scan inside the fence
                i += 1
                continue
            head = heading(L, i)
            path = header_path(info) or header_path(head)
            explicit = bool(HEADER.match(head))
            lang = info.split(" ")[0].lower()
            code = [x for x in body if x.strip() and not x.strip().startswith(("#", "REM ", "::"))]
            if not explicit and code and (lang in SHELL - {"text", "output"} or (not lang and all(CMD.match(x.strip())
                                                                                            for x in code))):
                for x in code:
                    command(x)
                i = j + 1
                continue
            if not path and last_path and last_path.endswith(".py") and body and CODE.match(body[0]):
                ops.append(insert_op(last_path, body, head))
            elif path and (info.split(" ")[0].lower() not in SHELL or explicit):
                if explicit and DELETE.search(head):
                    ops.append(Op("delete", path, None, head, True))
                else:
                    ops.append(Op("write", path, body, head or info, explicit))
            i = j + 1
            continue
        if HEADER.match(s) and header_path(s):
            p = header_path(s)
            if DELETE.search(s):
                ops.append(Op("delete", p, None, s, True))
                i += 1
                continue
            j = i + 1
            while j < len(L) and not L[j].strip():
                j += 1
            if j >= len(L) or L[j].strip().startswith("```") or is_boundary(L, j):
                last_path = p  # the fence / diff below picks it up
                i += 1
                continue
            k = j
            while k < len(L) and not is_boundary(L, k):
                k += 1
            body = L[j:k]
            while body and not body[-1].strip():
                body.pop()
            ops.append(Op("write", p, body, s, True))
            i = k
            continue
        if not s[:1].isspace() and command(s):
            i += 1
            continue
        if s[:1] in " +-" and last_path:
            k = bare_end(L, i)
            if k:
                ops.append(Op("diff", last_path, bare_hunks(L[i:k]), "diff (no header): " + last_path))
                i = k
                continue
        if last_path and last_path.endswith(".py") and MODSTART.match(s):
            k = module_end(L, i)
            if k:
                body = L[i:k]
                while body and not body[-1].strip():
                    body.pop()
                ops.append(Op("write", last_path, body, last_line, bool(WHOLE.search(last_line))))
                i = k
                continue
        if last_path and last_path.endswith(".py") and CODE.match(s):
            k = i + 1
            while k < len(L) and not is_boundary(L, k) and not (
                    L[k].strip() and not L[k][0].isspace() and not re.match(r"[@#)]|" + CODE.pattern, L[k])):
                k += 1
            body = L[i:k]
            while body and not body[-1].strip():
                body.pop()
            ops.append(insert_op(last_path, body, heading(L, i)))
            i = k
            continue
        p = path_only(s) or (header_path(re.sub(r"\([^)]*\)", "", s)) if SECTION.search(s) else None)
        if p:
            last_path, last_line = p, s
        i += 1
    return ops


# ---------------------------------------------------------------- matching

def locate(lines, block, hint, pos):
    """(index, how, hits) of block in lines, preferring after pos and near hint."""
    n = len(block)
    if not n:
        return max(0, min(hint, len(lines))), "no context", 1
    for how, f in NORMS:
        nl, nb = [f(x) for x in lines], [f(x) for x in block]
        hits = [k for k in range(len(nl) - n + 1) if nl[k] == nb[0] and nl[k:k + n] == nb]
        if hits:
            return min(hits, key=lambda h: (h < pos, abs(h - hint))), how, len(hits)
    return None


def blank_split(body):
    """Parts of a hunk between blank lines, keeping only parts that change something."""
    parts, cur = [], []
    for x in body + [""]:
        if x.strip():
            cur.append(x)
        else:
            if any(y[:1] in "+-" for y in cur):
                parts.append(cur)
            cur = []
    return parts


def apply_hunks(text, hunks):
    lines, delta, pos, notes, changed, failed = text.split("\n"), 0, 0, [], False, []
    strip_set = {x.strip() for x in lines}
    queue = [(str(k), a, body) for k, (a, body) in enumerate(hunks, 1)]
    while queue:
        hn, a, body = queue.pop(0)
        old =[x[1:] for x in body if not x.startswith("+")]
        new = [x[1:] for x in body if not x.startswith("-")]
        hint = a - 1 + delta if a else pos
        lead = next((k for k, x in enumerate(body) if x[:1] in "+-"), len(body))
        tail = next((k for k, x in enumerate(reversed(body)) if x[:1] in "+-"), len(body))
        r = applied = None
        for t in (0, 1, 2, 3):  # drop up to 3 context lines per end: AIs often get the outer context wrong
            lt, tt = min(t, lead), min(t, tail)
            o2, n2 = old[lt:len(old) - tt], new[lt:len(new) - tt]
            if t and (lt + tt == 0 or sum(bool(x.strip()) for x in o2) < 2):  # keep 2+ real anchor lines
                break
            r = locate(lines, o2, hint, pos)
            if r is None and n2 and n2 != o2 and locate(lines, n2, hint, 0) and not (
                    not any(x[:1] == "+" for x in body) and any(x[1:].strip() in strip_set for x in body
                                                                if x[:1] == "-" and x[1:].strip())):  # pure deletion still present
                applied = True
            if r or applied:
                break
        if applied:
            notes.append("hunk %s: already applied" % hn)
            continue
        if r is None:
            parts = blank_split(body)
            if len(parts) > 1 or (parts and parts[0] != body):  # blank lines often separate distant edits
                notes.append("hunk %s: split at blank lines into %d part(s)" % (hn, len(parts)))
                queue[:0] = [("%s.%d" % (hn, k), a, p) for k, p in enumerate(parts, 1)]
                continue
            failed.append("hunk %s NOT applied: its lines were not found (near line %s)" % (hn, a or "?"))
            continue
        k, how, hits = r
        if lt + tt:
            notes.append("hunk %s: matched without %d context line(s)" % (hn, lt + tt))
        if how in ("indent", "no context") or not any(x.strip() for x in o2):
            notes.append("hunk %s: %s, placed at line %d" % (hn, "matched ignoring indentation" if how == "indent"
                                                             else "weak context", k + 1))
        if hits > 1:
            notes.append("hunk %s: %d matches, used line %d" % (hn, hits, k + 1))
        lines[k:k + len(o2)] = n2
        delta += len(n2) - len(o2)
        pos = k + len(n2)
        changed = True
    if failed and not changed:
        raise ValueError("; ".join(x.replace(" NOT applied", "") for x in failed))
    return ("\n".join(lines) if changed else text), failed + notes  # partial apply: plan() marks it "check"


def apply_insert(text, block, where, name):
    """Put a top-level class/def block before/after the class/def called name."""
    if text is None:
        raise ValueError("file does not exist")
    lines = text.split("\n")
    if locate(lines, block, 0, 0):
        return text, []
    if block[0] in lines:
        raise ValueError("'%s' already exists with different code" % block[0].strip())
    if not where:
        raise ValueError("code block with no place to go (no 'before X' / 'after X' above it)")
    top = re.compile(r"(?:async\s+def|def|class)\s+%s\b" % re.escape(name))
    k = next((n for n, x in enumerate(lines) if top.match(x)), None)
    if k is None:
        raise ValueError("'%s' not found for 'insert %s'" % (name, where))
    if where == "before":
        while k > 0 and lines[k - 1].startswith(("@", "#")):
            k -= 1
        lines[k:k] = block + ["", ""]
    else:
        k += 1
        while k < len(lines) and (not lines[k].strip() or lines[k][0].isspace() or lines[k][0] == ")"):
            k += 1
        while k > 0 and not lines[k - 1].strip():
            k -= 1
        lines[k:k] = ["", ""] + block
    return "\n".join(lines), ["placed %s %s" % (where, name)]


def apply_replace(text, a, b):
    if not any(x.strip() for x in a):
        return ("\n".join(b) + "\n") if text is None else text.rstrip("\n") + "\n" + "\n".join(b) + "\n", []
    if text is None:
        raise ValueError("file does not exist")
    lines = text.split("\n")
    r = locate(lines, a, 0, 0)
    if r is None:
        if b and locate(lines, b, 0, 0):
            return text, ["already applied"]
        raise ValueError("SEARCH text not found")
    k, how, hits = r
    lines[k:k + len(a)] = b
    notes = ["%d matches, replaced the first" % hits] if hits > 1 else []
    return "\n".join(lines), notes + (["matched ignoring indentation"] if how == "indent" else [])


def syntax_error(path, text):
    ext = os.path.splitext(path)[1].lower()
    if text is None or ext not in (".py", ".json"):
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            compile(text, path, "exec") if ext == ".py" else json.loads(text)
    except (SyntaxError, ValueError) as e:
        return "%s (line %s)" % (getattr(e, "msg", e), getattr(e, "lineno", "?"))
    return None


# ---------------------------------------------------------------- files

def resolve(root, rel):
    rel = rel.strip().strip("`'\"").replace("\\", "/")
    root = os.path.normpath(os.path.abspath(root))
    full = os.path.normpath(os.path.join(root, rel))
    if os.path.isabs(rel) or os.path.commonpath([full, root]) != root:
        raise ValueError("path outside the project folder")
    if ".git" in os.path.relpath(full, root).split(os.sep):
        raise ValueError("refusing to touch .git")
    return full


def read_file(full):
    """(text with \\n endings or None, eol, bom)."""
    if not os.path.isfile(full):
        if os.path.exists(full):
            raise ValueError("path is a folder")
        return None, ("\r\n" if full.lower().endswith((".bat", ".cmd", ".ps1")) else "\n"), False
    try:
        raw = open(full, "rb").read()
    except OSError as e:
        raise ValueError("cannot read: %s" % e.strerror)
    bom = raw.startswith(codecs.BOM_UTF8)
    try:
        text = raw[3 if bom else 0:].decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("not a UTF-8 text file")
    return text.replace("\r\n", "\n"), ("\r\n" if "\r\n" in text else "\n"), bom


def plan(ops, root):
    """Fill op.before/after/status; return {full_path: (text|None, eol, bom)} after all enabled ops."""
    state, disk = {}, {}
    for op in ops:
        op.note, op.before, op.after = "", None, None
        if op.kind == "run":  # runs after the files are written; only known-safe commands are ticked
            op.status = "run" if AUTO.match(op.data) else "cmd"
            continue
        try:
            if not op.path:
                raise ValueError("no file path found above this block")
            full = resolve(root, op.path)
            if full not in disk:
                disk[full] = read_file(full)
                state[full] = disk[full][0]
            cur = state[full]
            notes = []
            if op.kind == "write":
                new = "\n".join(op.data).rstrip("\n") + "\n"
            elif op.kind == "delete":
                new = None
            elif op.kind == "diff":
                if cur is None:
                    raise ValueError("file does not exist")
                new, notes = apply_hunks(cur, op.data)
            elif op.kind == "insert":
                new, notes = apply_insert(cur, *op.data)
            else:
                new, notes = apply_replace(cur, *op.data)
            status = "applied" if new == cur else "new" if cur is None else "delete" if new is None else \
                "replace" if op.kind == "write" else "fuzzy" if notes else "ok"
            if op.kind == "diff" and any("NOT applied" in x for x in notes):
                status = "check"
            if op.kind == "write" and status != "applied":
                ph = next((x.strip() for x in op.data if PLACEHOLDER.search(x)), None)
                a, b = (cur or "").count("\n"), new.count("\n")
                if ph:
                    status = "check"
                    notes.append("contains an AI placeholder line: %s" % ph[:70])
                elif cur is not None and not op.explicit:
                    status = "check"
                    notes.append("replaces the whole file (%d -> %d lines)" % (a, b))
                elif cur is not None and b < a * 0.5:
                    status = "check"
                    notes.append("shrinks the file from %d to %d lines" % (a, b))
            err = syntax_error(op.path, new) if status != "applied" else None
            if err and not syntax_error(op.path, cur):
                status = "broken"
                notes.append("would break the file: " + err)
            if op.superseded:
                notes.append("unticked: block %d further down redoes this edit" % op.superseded)
            op.before, op.after, op.status, op.note = cur, new, status, "; ".join(notes)
            if op.enabled:
                state[full] = new
        except ValueError as e:
            op.status, op.note = "error", str(e)
    return {f: (state[f],) + disk[f][1:] for f in state if state[f] != disk[f][0]}


def default_ticks(ops, root):
    for op in ops:
        op.enabled, op.superseded, op.tried = True, None, False
    while True:  # unticking one block can change how later blocks on the same file land
        plan(ops, root)
        drop = [op for op in ops if op.enabled and op.status not in GOOD]
        for op in drop:
            op.enabled = False
        if not drop and not supersede(ops, root):
            return plan(ops, root)


def supersede(ops, root):
    """A failed block that applies once an earlier block on the same file is unticked replaces it."""
    for k, x in enumerate(ops):
        failed = x.status == "error" or (x.status == "check" and x.kind == "diff")  # "check" diff = partly failed
        if x.enabled or not failed or x.tried or not x.path or x.kind == "run":
            continue
        x.tried = True
        for y in reversed(ops[:k]):
            if y.enabled and y.path == x.path:
                y.enabled, x.enabled = False, True
                plan(ops, root)
                if x.status in GOOD:
                    y.superseded = k + 1
                    return True
                y.enabled, x.enabled = True, False
    return False


def file_hash(full):
    return hashlib.sha1(open(full, "rb").read()).hexdigest() if os.path.isfile(full) else None


def write_all(changes, root):
    """Back up, then write every change atomically. Returns the relative paths written."""
    if not changes:
        return []
    stamp = time.strftime("%Y%m%d-%H%M%S")
    d, n = os.path.join(BACKUPS, stamp), 1
    while os.path.exists(d):
        n += 1
        d = os.path.join(BACKUPS, "%s-%d" % (stamp, n))
    os.makedirs(d)
    man = {"root": root, "files": {}, "after": {}}
    for k, full in enumerate(changes):
        man["files"][full] = None
        if os.path.isfile(full):
            shutil.copy2(full, os.path.join(d, "f%d" % k))
            man["files"][full] = "f%d" % k
    mpath = os.path.join(d, "manifest.json")
    try:
        for full, (text, eol, bom) in changes.items():
            if text is None:
                if os.path.isfile(full):
                    os.remove(full)
            else:
                os.makedirs(os.path.dirname(full), exist_ok=True)
                tmp = full + ".pasteapply.tmp"
                with open(tmp, "wb") as fh:
                    fh.write((codecs.BOM_UTF8 if bom else b"") + text.replace("\n", eol).encode("utf-8"))
                os.replace(tmp, full)
            man["after"][full] = file_hash(full)
    finally:
        with open(mpath, "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=1)
    return [os.path.relpath(f, root) for f in changes]


def last_backup():
    """(stamp, dir, manifest, files edited since that apply) or None."""
    names = sorted(x for x in os.listdir(BACKUPS) if os.path.isfile(os.path.join(BACKUPS, x, "manifest.json"))) \
        if os.path.isdir(BACKUPS) else []
    if not names:
        return None
    d = os.path.join(BACKUPS, names[-1])
    man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
    edited = [f for f, h in man.get("after", {}).items() if file_hash(f) != h]
    return names[-1], d, man, edited


def undo():
    """Restore the newest backup; returns (stamp, [paths])."""
    got = last_backup()
    if not got:
        return None, []
    stamp, d, man, _ = got
    for full, blob in man["files"].items():
        if blob is None:
            if os.path.isfile(full):
                os.remove(full)
        else:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            shutil.copy2(os.path.join(d, blob), full)
    shutil.rmtree(d)
    return stamp, list(man["files"])


def local_cmd(cmd, root):
    """Point python/py/pytest at the project's .venv when it has one (the exe has no python of its own)."""
    exe, _, rest = cmd.partition(" ")
    win = os.name == "nt"
    if exe in ("python", "python3", "py", "pytest"):
        name = "pytest" if exe == "pytest" else "python"
        v = os.path.join(root, ".venv", "Scripts" if win else "bin", name + (".exe" if win else ""))
        if os.path.isfile(v):
            exe = '"%s"' % v if win else v
    return exe + (" " + rest if rest else "")


def recent_images(root, since):
    found = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in NO_SCAN and not x.startswith(".")]
        for f in files:
            if f.lower().endswith(IMAGES):
                full = os.path.join(d, f)
                try:
                    if os.path.getmtime(full) >= since - 1:
                        found.append(full)
                except OSError:
                    pass
    return sorted(found)


def run_all(cmds, root, out, proc=None):
    """Run each command in root, streaming lines to out(text, tag). Returns how many failed.
    Tags: "cmd", "ok", "bad", None, or ("file", full_path) for images the commands wrote."""
    proc = {} if proc is None else proc
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    since, bad = time.time(), 0
    for cmd in cmds:
        if proc.get("stop"):
            out("stopped\n", "bad")
            return bad + 1
        out("$ %s\n" % cmd, "cmd")
        t0 = time.time()
        try:
            line = local_cmd(cmd, root)
            p = subprocess.Popen(line if os.name == "nt" else __import__("shlex").split(line), cwd=root,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as e:
            out("could not start: %s\n\n" % e, "bad")
            bad += 1
            continue
        proc["p"] = p
        for raw in p.stdout:
            out(raw.decode("utf-8", "replace").replace("\r\n", "\n"), None)
        code = p.wait()
        proc["p"] = None
        bad += code != 0
        out("exit %d (%.1fs)\n\n" % (code, time.time() - t0), "ok" if code == 0 else "bad")
    imgs = recent_images(root, since)
    if imgs:
        out("%d image(s) written:\n" % len(imgs), "cmd")
        for f in imgs[:60]:
            out(os.path.relpath(f, root) + "\n", ("file", f))
        if len(imgs) > 60:
            out("... %d more\n" % (len(imgs) - 60), None)
    out("done: %d command(s), %d failed\n" % (len(cmds), bad), "ok" if not bad else "bad")
    return bad


def report(ops):
    out = []
    for k, op in enumerate(ops, 1):
        out.append("[%s] %2d %-7s %-8s %s%s" % ("x" if op.enabled else " ", k, op.kind, op.status, op.path or op.label,
                                               ("  - " + op.note) if op.note else ""))
    return "\n".join(out)


def op_lines(op, limit=6000):
    """Preview lines: the resulting diff, or what the block wanted when it can't apply."""
    if op.kind == "run":
        return ["$ " + op.data, "", "Runs in the project folder after Apply; output shows in the Terminal tab."]
    if op.status == "error":
        if op.kind == "diff":
            return [ln for a, body in op.data for ln in ["@@ near line %s @@" % (a or "?")] + body]
        if op.kind == "insert":
            return ["+" + x for x in op.data[0]]
        if op.kind == "replace":
            return ["@@ SEARCH @@"] + ["-" + x for x in op.data[0]] + ["@@ REPLACE @@"] + ["+" + x for x in op.data[1]]
        return ["+" + x for x in (op.data or [])]
    a = [] if op.before is None else op.before.split("\n")
    b = [] if op.after is None else op.after.split("\n")
    d = list(difflib.unified_diff(a, b, n=3, lineterm=""))[2:]
    return d[:limit] + (["... (%d more lines)" % (len(d) - limit)] if len(d) > limit else [])


# ---------------------------------------------------------------- GUI

def load_settings():
    try:
        return json.load(open(SETTINGS, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(**kw):
    s = load_settings()
    s.update(kw)
    os.makedirs(DATA, exist_ok=True)
    with open(SETTINGS, "w", encoding="utf-8") as fh:
        json.dump(s, fh)


def windows_dark():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except (ImportError, OSError):
        return False


THEMES = {
    "light": dict(bg="#eef0f3", card="#ffffff", field="#fafbfc", line="#d8dce2", fg="#1f2328", dim="#656d76",
                  faint="#8c959f", acc="#2563eb", acc_hi="#1d4ed8", acc_off="#a9c0f2", acc_off_fg="#f2f5fc",
                  hover="#f3f4f6", sel="#e1ebfd", text_sel="#cfe0fc", thumb="#cdd2d9", thumb_hi="#aeb5bf",
                  na_fill="#eceef1", na_edge="#d0d4da", amber="#9a6700", red="#cf222e",
                  add=("#116329", "#e6ffec"), dele=("#82071e", "#ffebe9"), hunk=("#6e7781", "#f3f4f6")),
    "dark": dict(bg="#16181d", card="#1e2128", field="#1a1d23", line="#2e333d", fg="#e6e8ec", dim="#9aa2ae",
                 faint="#6b7280", acc="#3b82f6", acc_hi="#2f6fe0", acc_off="#24395f", acc_off_fg="#7b8bab",
                 hover="#282c35", sel="#233350", text_sel="#2b4a7a", thumb="#3a404b", thumb_hi="#4d5462",
                 na_fill="#262a32", na_edge="#363b46", amber="#e3b341", red="#f47067",
                 add=("#7ee2a0", "#15301f"), dele=("#ff9b9b", "#3a1d20"), hunk=("#8b949e", "#23272f")),
}


def gui(root, text=None, shot=None, row=0, ticks=None, theme=None):
    import tkinter as tk
    import traceback
    from tkinter import filedialog, messagebox, ttk

    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    theme = theme or load_settings().get("theme") or ("dark" if windows_dark() else "light")
    P = THEMES[theme]
    BG, CARD, FIELD, LINE, FG, DIM, ACC = (P[k] for k in ("bg", "card", "field", "line", "fg", "dim", "acc"))
    WHAT = {"ok": "Edit", "new": "New file", "replace": "Replace file", "delete": "Delete file",
            "fuzzy": "Edit (loose match)", "check": "Check first", "broken": "Would break code",
            "applied": "Already done", "error": "Can't apply", "run": "Command", "cmd": "Command (check)"}
    TINT = {"cmd": P["amber"], "fuzzy": P["amber"], "check": P["amber"], "broken": P["red"], "error": P["red"], "applied": P["faint"]}

    w = tk.Tk()
    w.withdraw()
    w.title("Paste Apply")
    px = w.winfo_fpixels("1i") / 96.0

    def S(v):
        return int(round(v * px))

    w.geometry("%dx%d" % (S(1200), S(780)))
    w.minsize(S(860), S(540))
    w.configure(bg=BG)
    ico = os.path.join(getattr(sys, "_MEIPASS", HERE), "paste_apply.ico")
    if os.path.isfile(ico):
        try:
            w.iconbitmap(ico)
        except tk.TclError:
            pass
    w.report_callback_exception = lambda *a: messagebox.showerror(
        "Paste Apply", "Something went wrong (no files were touched by this error):\n\n" +
        "".join(traceback.format_exception(*a))[-1200:])

    base, bold, mono = ("Segoe UI", 10), ("Segoe UI Semibold", 10), ("Consolas", 10)
    st = ttk.Style(w)
    st.theme_use("clam")
    st.configure(".", background=BG, foreground=FG, font=base, bordercolor=LINE, lightcolor=BG, darkcolor=BG,
                 focuscolor=BG)
    st.configure("Card.TFrame", background=CARD)
    st.configure("Card.TLabel", background=CARD)
    st.configure("Step.TLabel", background=CARD, font=("Segoe UI Semibold", 11))
    st.configure("Note.TLabel", background=CARD, foreground=DIM)
    st.configure("Dim.TLabel", foreground=DIM)
    st.configure("Title.TLabel", font=("Segoe UI Semibold", 15))
    st.configure("TButton", background=CARD, bordercolor=LINE, lightcolor=CARD, darkcolor=CARD,
                 padding=(S(12), S(4)))
    st.configure("TButton", foreground=FG)
    st.map("TButton", background=[("active", P["hover"])], lightcolor=[("active", P["hover"])],
           darkcolor=[("active", P["hover"])])
    st.configure("Link.TButton", background=BG, foreground=ACC, bordercolor=BG, lightcolor=BG, darkcolor=BG,
                 padding=(S(4), S(2)))
    st.map("Link.TButton", background=[("active", BG)], lightcolor=[("active", BG)], foreground=[("active", P["acc_hi"])])
    st.configure("Accent.TButton", background=ACC, foreground="white", bordercolor=ACC, lightcolor=ACC, darkcolor=ACC,
                 padding=(S(20), S(6)), font=bold)
    off, hi = P["acc_off"], P["acc_hi"]
    st.map("Accent.TButton", background=[("disabled", off), ("active", hi)], bordercolor=[("disabled", off)],
           lightcolor=[("disabled", off), ("active", hi)], darkcolor=[("disabled", off), ("active", hi)],
           foreground=[("disabled", P["acc_off_fg"])])
    st.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=FG, rowheight=S(30), borderwidth=0)
    st.map("Treeview", background=[("selected", P["sel"])], foreground=[("selected", FG)])
    st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    for o in ("Vertical", "Horizontal"):  # slim, arrowless scrollbars
        st.layout(o + ".TScrollbar", [(o + ".Scrollbar.trough", {"sticky": "nswe", "children": [
            (o + ".Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        st.configure(o + ".TScrollbar", troughcolor=FIELD, background=P["thumb"], bordercolor=FIELD,
                     lightcolor=P["thumb"], darkcolor=P["thumb"], gripcount=0, arrowsize=S(9))
        st.map(o + ".TScrollbar", background=[("active", P["thumb_hi"])])
    # same size, invisible: hides a vertical bar without changing the width the text wraps to
    st.configure("Ghost.Vertical.TScrollbar", background=FIELD, lightcolor=FIELD, darkcolor=FIELD)
    st.configure("TabOn.TButton", background=CARD, foreground=FG, bordercolor=CARD, lightcolor=CARD, darkcolor=CARD,
                 padding=(S(2), S(2), S(10), S(2)), font=bold)
    st.configure("TabOff.TButton", background=CARD, foreground=DIM, bordercolor=CARD, lightcolor=CARD, darkcolor=CARD,
                 padding=(S(2), S(2), S(10), S(2)))
    for t in ("TabOn", "TabOff"):
        st.map(t + ".TButton", background=[("active", CARD)], lightcolor=[("active", CARD)],
               darkcolor=[("active", CARD)], foreground=[("active", ACC)])
    st.map("Ghost.Vertical.TScrollbar", background=[("active", FIELD)])

    def box_img(fill, edge, tick):
        n = S(16)
        im = tk.PhotoImage(width=n, height=n)
        im.put(edge, to=(0, 0, n, n))
        im.put(fill, to=(1, 1, n - 1, n - 1))
        if tick:
            th = max(2, n // 8)
            for k in range(n * 3):
                t = k / (n * 3.0)
                x, y = ((0.22 + 0.2 * t / 0.35, 0.5 + 0.2 * t / 0.35) if t < 0.35 else
                        (0.42 + 0.36 * (t - 0.35) / 0.65, 0.7 - 0.42 * (t - 0.35) / 0.65))
                x, y = int(x * n - th / 2), int(y * n - th / 2)
                im.put("#ffffff", to=(x, y, x + th, y + th))
        return im

    imgs = {"on": box_img(ACC, ACC, True), "off": box_img(CARD, P["faint"], False),
            "na": box_img(P["na_fill"], P["na_edge"], False)}
    ui = {"root": root, "ops": [], "job": None, "proc": None}

    # header
    head = ttk.Frame(w, padding=(S(20), S(14), S(20), S(10)))
    head.pack(fill="x")
    ttk.Label(head, text="Paste Apply", style="Title.TLabel").pack(side="left")
    theme_btn = ttk.Button(head, text="Light mode" if theme == "dark" else "Dark mode", style="Link.TButton")
    theme_btn.pack(side="right")
    ttk.Label(head, text="|", style="Dim.TLabel").pack(side="right", padx=S(6))
    root_btn = ttk.Button(head, text="Change folder", style="Link.TButton")
    root_btn.pack(side="right")
    root_lbl = ttk.Label(head, style="Dim.TLabel")
    root_lbl.pack(side="right", padx=(0, S(4)))

    # footer (packed before the cards so it never gets squeezed off)
    foot = ttk.Frame(w, padding=(S(20), S(12), S(20), S(16)))
    foot.pack(side="bottom", fill="x")
    apply_btn = ttk.Button(foot, text="Apply", style="Accent.TButton")
    apply_btn.pack(side="right")
    undo_btn = ttk.Button(foot, text="Undo last apply")
    undo_btn.pack(side="right", padx=S(10))
    report_btn = ttk.Button(foot, text="Copy report", style="Link.TButton")
    report_btn.pack(side="right")
    status = ttk.Label(foot, style="Dim.TLabel")
    status.pack(side="left")

    main = ttk.Frame(w, padding=(S(20), 0))
    main.pack(fill="both", expand=True)
    main.columnconfigure(0, weight=5, uniform="c")
    main.columnconfigure(1, weight=6, uniform="c")
    main.rowconfigure(0, weight=1)

    def card(col, title):
        outer = tk.Frame(main, bg=LINE)
        outer.grid(row=0, column=col, sticky="nsew", padx=(0, S(14)) if col == 0 else 0)
        c = ttk.Frame(outer, style="Card.TFrame", padding=(S(16), S(12), S(16), S(14)))
        c.pack(fill="both", expand=True, padx=1, pady=1)
        ttk.Label(c, text=title, style="Step.TLabel").pack(anchor="w", pady=(0, S(10)))
        return c

    def autohide(sb):
        def set_(a, b):
            sb.grid_remove() if float(a) <= 0 and float(b) >= 1 else sb.grid()
            sb.set(a, b)
        return set_

    def ghost(sb):
        def set_(a, b):
            sb.configure(style="Ghost.Vertical.TScrollbar" if float(a) <= 0 and float(b) >= 1 else "Vertical.TScrollbar")
            sb.set(a, b)
        return set_

    def text_box(parent, wrap, **kw):
        f = tk.Frame(parent, bg=LINE)
        inner = tk.Frame(f, bg=FIELD)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        inner.rowconfigure(0, weight=1)
        inner.columnconfigure(0, weight=1)
        t = tk.Text(inner, bg=FIELD, fg=FG, insertbackground=FG, font=mono, wrap=wrap, relief="flat", bd=0,
                    padx=S(10), pady=S(8), selectbackground=P["text_sel"], selectforeground=FG,
                    highlightthickness=0, **kw)
        t.grid(row=0, column=0, sticky="nsew")
        ys = ttk.Scrollbar(inner, command=t.yview)
        ys.grid(row=0, column=1, sticky="ns", padx=(0, S(2)), pady=S(2))
        t.configure(yscrollcommand=ghost(ys))
        if wrap == "none":
            xs = ttk.Scrollbar(inner, orient="horizontal", command=t.xview)
            xs.grid(row=1, column=0, sticky="ew", padx=S(2), pady=(0, S(2)))
            t.configure(xscrollcommand=autohide(xs))
        return f, t

    left = card(0, "1   Paste the AI's answer")
    right = card(1, "2   Check the changes, then apply")

    lbar = ttk.Frame(left, style="Card.TFrame")
    lbar.pack(side="bottom", fill="x", pady=(S(10), 0))
    lf, inp = text_box(left, "word", undo=True)
    lf.pack(fill="both", expand=True)
    hint = tk.Label(inp, text="Copy the AI's whole reply and press Ctrl+V here.\n\n"
                              "Diffs, new files, whole files and search/replace\nblocks are picked out automatically.",
                    bg=FIELD, fg=P["faint"], font=base, justify="left")
    paste_btn = ttk.Button(lbar, text="Paste from clipboard")
    paste_btn.pack(side="left")
    clear_btn = ttk.Button(lbar, text="Clear")
    clear_btn.pack(side="left", padx=S(8))

    tf = tk.Frame(right, bg=LINE)
    tf.pack(fill="x")
    tree = ttk.Treeview(tf, columns=("file", "what"), show="tree", selectmode="browse", height=7)
    tree.column("#0", width=S(40), minwidth=S(40), stretch=False, anchor="center")
    tree.column("file", width=S(300), stretch=True)
    tree.column("what", width=S(140), stretch=False)
    for s, c in TINT.items():
        tree.tag_configure(s, foreground=c)
    tf.rowconfigure(0, weight=1)
    tf.columnconfigure(0, weight=1)
    tree.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
    tys = ttk.Scrollbar(tf, command=tree.yview)
    tys.grid(row=0, column=1, sticky="ns", padx=(0, 1), pady=1)
    tree.configure(yscrollcommand=autohide(tys))
    empty = tk.Label(tf, text="Nothing found yet.", bg=CARD, fg=P["faint"], font=base)
    detail = ttk.Label(right, style="Note.TLabel", justify="left")
    detail.pack(fill="x", pady=(S(10), S(6)))
    tabs = ttk.Frame(right, style="Card.TFrame")
    tabs.pack(fill="x", pady=(0, S(4)))
    tab_changes = ttk.Button(tabs, text="Changes", style="TabOn.TButton")
    tab_changes.pack(side="left")
    tab_term = ttk.Button(tabs, text="Terminal", style="TabOff.TButton")
    tab_term.pack(side="left")
    stop_btn = ttk.Button(tabs, text="Stop", style="Link.TButton")
    pane = ttk.Frame(right, style="Card.TFrame")
    pane.pack(fill="both", expand=True)
    pf, prev = text_box(pane, "none")
    pf.pack(fill="both", expand=True)
    termf, term = text_box(pane, "char")
    for tag, c in (("cmd", ACC), ("ok", P["add"][0]), ("bad", P["red"]), ("file", ACC)):
        term.tag_configure(tag, foreground=c)
    term.tag_configure("file", underline=True)
    term.tag_bind("file", "<Enter>", lambda e: term.configure(cursor="hand2"))
    term.tag_bind("file", "<Leave>", lambda e: term.configure(cursor=""))
    term.insert("end", "Commands from the paste (python tools/..., pytest, ...) run here after Apply.\n", "cmd")
    term.configure(state="disabled")

    def tab(name):
        on = name == "term"
        (pf if on else termf).pack_forget()
        (termf if on else pf).pack(fill="both", expand=True)
        tab_term.configure(style="TabOn.TButton" if on else "TabOff.TButton")
        tab_changes.configure(style="TabOff.TButton" if on else "TabOn.TButton")
    for tag, (c, bg) in (("add", P["add"]), ("del", P["dele"]), ("hunk", P["hunk"])):
        prev.tag_configure(tag, foreground=c, background=bg)
    prev.configure(state="disabled")
    right.bind("<Configure>", lambda e: detail.configure(wraplength=max(100, e.width - S(40))))

    def say(msg):
        status.configure(text=msg)

    def show(op):
        prev.configure(state="normal")
        prev.delete("1.0", "end")
        if op is None:
            detail.configure(text="")
        else:
            detail.configure(text="%s  -  %s%s" % (op.path or op.label, WHAT.get(op.status, op.status),
                                                   (".  " + op.note[0].upper() + op.note[1:]) if op.note else ""))
            for ln in op_lines(op):
                tag = "hunk" if ln.startswith("@@") else "add" if ln.startswith("+") else \
                    "del" if ln.startswith("-") else ""
                prev.insert("end", ln + "\n", tag)
        prev.configure(state="disabled")

    def refresh(keep=None):
        tree.delete(*tree.get_children())
        ops = ui["ops"]
        tree.configure(height=min(max(len(ops), 4), 9))
        for k, op in enumerate(ops):
            img = imgs["na"] if op.status in ("error", "applied") else imgs["on" if op.enabled else "off"]
            tree.insert("", "end", iid=str(k), image=img, values=(op.path or op.label, WHAT.get(op.status, op.status)),
                        tags=(op.status,))
        if ops:
            empty.place_forget()
            k = keep if keep is not None and keep < len(ops) else 0
            tree.selection_set(str(k))
            tree.see(str(k))
            show(ops[k])
        else:
            empty.place(relx=0.5, rely=0.5, anchor="center")
            show(None)
        runs = [op for op in ops if op.kind == "run" and op.enabled]
        on = [op for op in ops if op.enabled and op.status in GOOD and op.kind != "run"]
        files = len({op.path for op in on})
        label = "Apply %d change%s" % (len(on), "" if len(on) == 1 else "s") if on else "Apply"
        if runs:
            n = "%d command%s" % (len(runs), "" if len(runs) == 1 else "s")
            label = label + " + run " + n if on else "Run " + n
        apply_btn.configure(text=label, state="normal" if (on or runs) and not ui["proc"] else "disabled")
        ops = [op for op in ops if op.kind != "run"]
        bad = sum(op.status in ("error", "broken", "check") for op in ops)
        miss = [op for op in ops if op.status == "error" and "does not exist" in op.note]
        if not ui["ops"]:
            say("Waiting for a paste." if not inp.get("1.0", "end-1c").strip() else
                "No changes found in this text.")
        elif miss and len(miss) == sum(op.kind in ("diff", "replace") for op in ops):
            say("None of the edited files exist here. Is the project folder right?")
        else:
            say("%d change%s found%s%s." % (len(ops), "" if len(ops) == 1 else "s",
                                            ", %d ticked in %d file%s" % (len(on), files, "" if files == 1 else "s")
                                            if on else "", ", %d need%s a look" % (bad, "s" if bad == 1 else "")
                                            if bad else "") +
                ("  %d command%s ticked to run after." % (len(runs), "" if len(runs) == 1 else "s") if runs else ""))

    def reparse():
        ui["job"] = None
        ui["ops"] = parse(inp.get("1.0", "end-1c"))
        default_ticks(ui["ops"], ui["root"])
        refresh()

    def sync_hint():
        if inp.get("1.0", "1.end") or inp.index("end-1c") != "1.0":
            hint.place_forget()
        else:
            hint.place(x=S(10), y=S(8))

    def on_change(_e=None):
        if inp.edit_modified():
            inp.edit_modified(False)
            sync_hint()
            if ui["job"]:
                w.after_cancel(ui["job"])
            ui["job"] = w.after(300, reparse)

    def selected():
        sel = tree.selection()
        return int(sel[0]) if sel else None

    def toggle(k):
        if k is None or ui["ops"][k].status in ("error", "applied"):
            return
        ui["ops"][k].enabled = not ui["ops"][k].enabled
        plan(ui["ops"], ui["root"])
        refresh(k)

    def on_click(e):
        r = tree.identify_row(e.y)
        if r and tree.identify_column(e.x) == "#0":
            tree.selection_set(r)
            toggle(int(r))
            return "break"

    def paste_clip():
        try:
            txt = w.clipboard_get()
        except tk.TclError:
            return say("The clipboard is empty.")
        inp.delete("1.0", "end")
        inp.insert("1.0", txt)

    def set_root():
        p = filedialog.askdirectory(title="Project folder", initialdir=ui["root"])
        if p:
            ui["root"] = os.path.normpath(p)
            save_settings(root=ui["root"])
            root_lbl.configure(text="Project folder:  " + ui["root"])
            reparse()

    def apply_now(_e=None):
        if str(apply_btn["state"]) == "disabled":
            return
        k = selected()
        changes = plan(ui["ops"], ui["root"])
        cmds = [op.data for op in ui["ops"] if op.kind == "run" and op.enabled]
        if not changes and not cmds:
            return say("Nothing to apply.")
        done = []
        if changes:
            try:
                done = write_all(changes, ui["root"])
            except OSError as e:
                messagebox.showerror("Paste Apply", "Writing failed: %s\n\nUse Undo last apply to put the files back."
                                     % e)
                return
            ticks = {id(op): op.enabled for op in ui["ops"] if op.kind == "run"}
            default_ticks(ui["ops"], ui["root"])
            for op in ui["ops"]:  # keep the user's command ticks for a re-run
                op.enabled = ticks.get(id(op), op.enabled)
        if cmds:
            start_run(cmds)
        refresh(k)
        if done:
            say("Applied to %d file%s: %s.  Undo puts them back." % (len(done), "" if len(done) == 1 else "s",
                                                                      ", ".join(done)))

    def term_out(text, tag):
        term.configure(state="normal")
        if isinstance(tag, tuple):
            link = "f%s" % term.index("end").split(".")[0]
            term.tag_bind(link, "<Button-1>", lambda e, f=tag[1]: os.startfile(f) if os.name == "nt" else None)
            term.insert("end", text, ("file", link))
        else:
            term.insert("end", text, tag or "")
        term.see("end")
        term.configure(state="disabled")

    def start_run(cmds):
        import queue
        import threading
        q, proc = queue.Queue(), {"stop": False, "p": None}
        ui["proc"] = proc
        term.configure(state="normal")
        term.delete("1.0", "end")
        term.configure(state="disabled")
        tab("term")
        stop_btn.pack(side="right")
        threading.Thread(target=lambda: q.put(("done", run_all(cmds, ui["root"], lambda t, g: q.put((t, g)), proc))),
                         daemon=True).start()

        def poll():
            while not q.empty():
                text, tag = q.get()
                if text == "done":
                    ui["proc"] = None
                    stop_btn.pack_forget()
                    refresh(selected())
                    return say("Commands finished: %s." % ("all OK" if not tag else "%d failed" % tag))
                term_out(text, tag)
            w.after(50, poll)
        say("Running %d command%s..." % (len(cmds), "" if len(cmds) == 1 else "s"))
        poll()

    def stop_run():
        proc = ui["proc"]
        if proc:
            proc["stop"] = True
            if proc.get("p"):
                try:
                    proc["p"].kill()
                except OSError:
                    pass

    def undo_now():
        got = last_backup()
        if not got:
            return say("Nothing to undo.")
        stamp, _d, man, edited = got
        names = "\n".join("  " + os.path.relpath(f, ui["root"]) for f in man["files"])
        msg = "Put these files back the way they were before the apply at %s?\n\n%s" % (stamp, names)
        if edited:
            msg += "\n\nThese changed again after that apply, and those later edits will be lost:\n" + \
                "\n".join("  " + os.path.relpath(f, ui["root"]) for f in edited)
        if not messagebox.askyesno("Undo last apply", msg, icon="warning" if edited else "question"):
            return
        _stamp, files = undo()
        default_ticks(ui["ops"], ui["root"])
        refresh(selected())
        say("Put back %d file%s." % (len(files), "" if len(files) == 1 else "s"))

    def copy_report():
        w.clipboard_clear()
        w.clipboard_append(report(ui["ops"]))
        say("Report copied. Paste it back to the AI to get fixes for the failed blocks.")

    def switch_theme():
        ui["text"] = inp.get("1.0", "end-1c")
        ui["ticks"] = [op.enabled for op in ui["ops"]]
        ui["row"] = selected() or 0
        ui["restart"] = "light" if theme == "dark" else "dark"
        save_settings(theme=ui["restart"])
        stop_run()
        w.destroy()

    root_btn.configure(command=set_root)
    theme_btn.configure(command=switch_theme)
    apply_btn.configure(command=apply_now)
    undo_btn.configure(command=undo_now)
    report_btn.configure(command=copy_report)
    stop_btn.configure(command=stop_run)
    tab_changes.configure(command=lambda: tab("changes"))
    tab_term.configure(command=lambda: tab("term"))
    w.protocol("WM_DELETE_WINDOW", lambda: (stop_run(), w.destroy()))
    paste_btn.configure(command=paste_clip)
    clear_btn.configure(command=lambda: inp.delete("1.0", "end"))
    hint.bind("<Button-1>", lambda e: inp.focus_set())
    inp.bind("<<Modified>>", on_change)
    tree.bind("<Button-1>", on_click)
    tree.bind("<<TreeviewSelect>>", lambda e: selected() is not None and show(ui["ops"][selected()]))
    tree.bind("<ButtonRelease-1>", lambda e: tree.identify_row(e.y) and tab("changes"))
    tree.bind("<space>", lambda e: toggle(selected()))
    inp.bind("<Control-Return>", lambda e: (apply_now(), "break")[1])  # no stray newline in the paste
    w.bind("<Control-Return>", apply_now)
    root_lbl.configure(text="Project folder:  " + ui["root"])
    if text:
        inp.insert("1.0", text)
        inp.edit_modified(False)
        reparse()
        if ticks and len(ticks) == len(ui["ops"]):
            for op, on in zip(ui["ops"], ticks):
                op.enabled = on and op.status not in ("error", "applied")
            plan(ui["ops"], ui["root"])
        if row or ticks:
            refresh(row)
    else:
        refresh()
    sync_hint()
    if os.name == "nt":  # title bar follows the theme (Windows 10 20H1+ / 11)
        try:
            import ctypes
            w.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(w.winfo_id())
            val = ctypes.c_int(1 if theme == "dark" else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
        except (AttributeError, OSError):
            pass
    w.deiconify()
    inp.focus_set()
    if shot:
        def grab():
            w.update()
            from PIL import ImageGrab
            x, y = w.winfo_rootx(), w.winfo_rooty()
            ImageGrab.grab((x, y, x + w.winfo_width(), y + w.winfo_height())).save(shot)
            w.destroy()
        w.attributes("-topmost", True)
        w.after(1200, grab)
    w.mainloop()
    if ui.get("restart"):  # theme switch rebuilds the window, keeping the paste, ticks and selection
        return gui(ui["root"], ui["text"], None, ui["row"], ui["ticks"], ui["restart"])


# ---------------------------------------------------------------- self test

def selftest():
    import tempfile
    global BACKUPS
    tmp = tempfile.mkdtemp()
    BACKUPS = os.path.join(tmp, "_bk")
    os.makedirs(os.path.join(tmp, "src"))
    with open(os.path.join(tmp, "src", "a.py"), "wb") as fh:
        fh.write(b"import os\r\n\r\n\r\ndef f():\r\n    return 1\r\n\r\n\r\ndef g():\r\n    return 2\r\n")
    with open(os.path.join(tmp, "old.txt"), "w") as fh:
        fh.write("bye\n")
    paste = "\n".join([
        "Here is the change. This creates a new file at src/zz.py later.",   # prose, not a header
        "1. New file: tools/new_tool.py",
        "",
        "#!/usr/bin/env python3",
        "# a comment, not a header",
        "print('hi')",
        "",
        "2. Patch: src/a.py",
        "",
        "--- a/src/a.py",
        "+++ b/src/a.py",
        "@@ -40,6 +40,7 @@",          # wrong line numbers on purpose
        " import os",
        "+import sys",
        "",                             # blank context that lost its space
        "",
        " def f():",
        "@@ -8,2 +9,2 @@",
        " def g():",
        "-    return 2",
        "+    return 3",
        "- not part of the diff, a bullet",
        "",
        "src/a.py",
        "<<<<<<< SEARCH",
        "        return 1",           # indentation drift
        "=======",
        "    return 10",
        ">>>>>>> REPLACE",
        "",
        "Delete file: old.txt",
        "",
        "### `notes/readme.md`",
        "```md",
        "# Notes",
        "```",
        "",
        "```bash",
        "python tools/new_tool.py",
        "```",
    ])
    ops = parse(paste)
    kinds = [(op.kind, op.path) for op in ops]
    assert kinds == [("write", "tools/new_tool.py"), ("diff", "src/a.py"), ("replace", "src/a.py"),
                     ("delete", "old.txt"), ("write", "notes/readme.md"), ("run", None)], kinds
    assert ops[-1].data == "python tools/new_tool.py" and ops[-1].enabled is not False
    assert ops[0].data[-1] == "print('hi')", ops[0].data
    changes = default_ticks(ops, tmp)
    assert [op.status for op in ops] == ["new", "ok", "fuzzy", "delete", "new", "run"], report(ops)
    write_all(changes, tmp)
    a = open(os.path.join(tmp, "src", "a.py"), "rb").read()
    assert a == b"import os\r\nimport sys\r\n\r\n\r\ndef f():\r\n    return 10\r\n\r\n\r\ndef g():\r\n    return 3\r\n", a
    assert not os.path.exists(os.path.join(tmp, "old.txt"))
    assert open(os.path.join(tmp, "notes", "readme.md")).read() == "# Notes\n"
    ops = parse(paste)
    assert not default_ticks(ops, tmp) and {op.status for op in ops if op.kind != "run"} == {"applied"}, report(ops)
    cmds = parse("Run:\n\n```bash\npython acaristan.py --dev-x\npytest -q\n```\npython -m compileall -q src\n")
    plan(cmds, tmp)
    assert [(op.data, op.status) for op in cmds] == [("python acaristan.py --dev-x", "cmd"), ("pytest -q", "run"),
                                                      ("python -m compileall -q src", "run")], report(cmds)
    got = []
    assert run_all(['python -c "print(42)"'], tmp, lambda t, g: got.append(t)) == 0 and "42\n" in got, got
    assert last_backup()[3] == []
    with open(os.path.join(tmp, "notes", "readme.md"), "a") as fh:
        fh.write("later edit\n")
    assert last_backup()[3] == [os.path.join(tmp, "notes", "readme.md")]
    stamp, files = undo()
    assert stamp and len(files) == 4, files
    assert open(os.path.join(tmp, "src", "a.py"), "rb").read().endswith(b"return 2\r\n")
    assert os.path.exists(os.path.join(tmp, "old.txt")) and not os.path.exists(os.path.join(tmp, "tools", "new_tool.py"))
    # held back: syntax break, placeholder, big shrink, unlabelled overwrite, escape from the root
    risky = "\n".join([
        "--- a/src/a.py", "+++ b/src/a.py", "@@ -4,2 +4,2 @@", " def f():", "-    return 1", "+    return (1",
        "", "Full file: src/a.py", "```python", "import os", "# ... rest of the file unchanged", "```",
        "", "Full file: src/a.py", "```python", "x = 1", "```",
        "", "### src/a.py", "```python", "def f():", "    return 5", "```",
        "", "--- a/../x.py", "+++ b/../x.py", "@@ -1 +1 @@", "-a", "+b",
    ])
    ops = parse(risky)
    changes = default_ticks(ops, tmp)
    assert [op.status for op in ops] == ["broken", "check", "check", "check", "error"], report(ops)
    assert not changes and "outside" in ops[-1].note and "placeholder" in ops[1].note and "shrinks" in ops[2].note
    # header-less diffs, a corrected restatement, a wrapped "--flag" prose line, a placed class
    with open(os.path.join(tmp, "b.py"), "w") as fh:
        fh.write("def a():\n    x = 1\n    return x\n\n\ndef b():\n    y = 2\n    return y\n\n\nclass C:\n    pass\n")
    bare = "\n".join([
        "Patch: b.py", "",
        " def a():", "     x = 1", "+    x += 1", "     return x", "",
        "Use this instead, so the second change also lands; also",
        "--dev-flag keeps working.)", "",
        " def a():", "     x = 1", "+    x += 5", "     return x",
        "...",
        " def b():", "     y = 2", "+    y += 1", "",
        "     return y", "",
        "Add it right after b, before C:", "",
        "class D:", "    pass", "",
        "- a bullet", "  wrapped",
    ])
    ops = parse(bare)
    assert [op.kind for op in ops] == ["diff", "diff", "insert"], report(ops)
    changes = default_ticks(ops, tmp)
    assert [op.enabled for op in ops] == [False, True, True] and ops[0].superseded == 2, report(ops)
    write_all(changes, tmp)
    b = open(os.path.join(tmp, "b.py")).read()
    assert "x += 5" in b and "x += 1" not in b and "y += 1" in b and b.index("class D") < b.index("class C"), b
    # an unfenced whole module under "Updated <path> (drop-in replacement)", prose after it
    mod = "\n".join([
        "Updated b.py (drop-in replacement)", "", "Some prose about it.", "",
        '"""Doc."""', "import os", "", "", "def a():", "    return os.sep", "", "",
        "X = 1", "", "Verification Commands", "", "python b.py",
    ])
    ops = parse(mod)
    assert [(op.kind, op.explicit, op.data[-1]) for op in ops[:1]] == [("write", True, "X = 1")], report(ops)
    assert [(op.kind, op.data) for op in ops[1:]] == [("run", "python b.py")], report(ops)
    ops = parse("Patch: b.py\n\nAdd after a:\n\ndef b():\n    return 0\n")
    default_ticks(ops, tmp)
    assert ops[0].status == "error" and "different code" in ops[0].note, report(ops)
    # wrong @@ counts mid-diff keep later hunks; a stale hunk and a stale pure deletion fail alone (partial = check)
    with open(os.path.join(tmp, "c.py"), "w") as fh:
        fh.write("A = 1\nB = 2\nC = 3\nK = 0\n\nD = 4\nE = 5\nF = 6\n\nG = 7\nH = 8\nI = 9\n")
    ops = parse("\n".join([
        "--- a/c.py", "+++ b/c.py",
        "@@ -1,2 +1,2 @@", " A = 1", "-B = 2", "+B = 20", " C = 3",
        "@@ -5,3 +5,3 @@", " D = 4", "-E = 5", "+E = 50", " F = 6",
        "@@ -9,3 +9,3 @@", " G = 7", "-X = 0", "+X = 1", " I = 9",
        "@@ -2,4 +2,2 @@", " B = 20", " C = 3", "-K = 0", "-Q = 1",
    ]))
    assert [op.kind for op in ops] == ["diff"] and len(ops[0].data) == 4, report(ops)
    default_ticks(ops, tmp)
    assert ops[0].status == "check" and "hunk 3 NOT" in ops[0].note and "hunk 4 NOT" in ops[0].note, report(ops)
    assert "E = 50" in ops[0].after and "B = 20" in ops[0].after and "K = 0" in ops[0].after, ops[0].after
    shutil.rmtree(tmp)
    print("PASTE APPLY SELFTEST: OK")


def main(argv):
    root = load_settings().get("root") or DEFAULT_ROOT
    if not os.path.isdir(root):
        root = DEFAULT_ROOT
    if "--root" in argv:
        root = argv[argv.index("--root") + 1]
    root = os.path.normpath(os.path.abspath(root))
    if "--selftest" in argv:
        return selftest()
    if "--undo" in argv:
        stamp, files = undo()
        print("restored %d file(s) from %s" % (len(files), stamp) if stamp else "no backups")
        return
    for flag in ("--check", "--apply"):
        if flag in argv:
            ops = parse(open(argv[argv.index(flag) + 1], encoding="utf-8").read())
            changes = default_ticks(ops, root)
            print(report(ops))
            if flag == "--apply":
                print("applied:", ", ".join(write_all(changes, root)) or "nothing")
                cmds = [op.data for op in ops if op.kind == "run" and op.enabled]
                if "--run" in argv and cmds:
                    return run_all(cmds, root, lambda t, _tag: print(t, end="", flush=True))
            return
    if "--shot" in argv:
        k = argv.index("--shot")
        theme = argv[argv.index("--theme") + 1] if "--theme" in argv else None
        rest = [a for a in argv[k + 1:] if a not in ("--theme", theme)]
        text = open(rest[1], encoding="utf-8").read() if len(rest) > 1 else None
        return gui(root, text, rest[0], int(rest[2]) if len(rest) > 2 and rest[2].isdigit() else 0, theme=theme)
    gui(root)


if __name__ == "__main__":
    main(sys.argv[1:])
