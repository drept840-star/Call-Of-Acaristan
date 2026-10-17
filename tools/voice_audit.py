"""Voice-line audit (polish pass T1).

Walks every module under src/ with ``ast`` (plus a regex pass for radio-style
'SPEAKER: "..."' literals stored in lists), finds every spoken line, resolves
it through the runtime matcher (audio.voice.find_line / has_file / clip
length), and cross-references Missing_voice_lines_by_character.xlsx so every
spreadsheet row ends up with a status.

    python tools/voice_audit.py            # writes validation/voice_audit.md + .csv
    python tools/voice_audit.py --check    # exit 1 if any manifest entry is
                                           # neither resolvable nor known-missing

Statuses: OK, FIXED (changed in the polish pass, see FIXED below),
REMOVED (spreadsheet row whose line no longer exists in code),
MISSING AUDIO (spoken line with no recording / no VO id),
NEEDS WRITER (line text needs a writing decision before it can be recorded).
Stdlib only (the xlsx is read with zipfile + ElementTree).
"""
import ast
import csv
import os
import re
import statistics
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
XLSX = ROOT / "Missing_voice_lines_by_character.xlsx"
OUT_MD = ROOT / "validation" / "voice_audit.md"
OUT_CSV = ROOT / "validation" / "voice_audit.csv"
sys.path.insert(0, str(SRC))
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from audio import voice  # noqa: E402
from audio.voice_manifest import VOICE_LINES  # noqa: E402

# Lines changed by the polish pass (normalized text -> note).
FIXED = {}
# Clips that are long on purpose (scream recorded onto the end of the line).
BAKED_SCREAMS = {"VO_110", "VO_116"}
# Lines whose text needs a writer before recording (normalized -> note).
NEEDS_WRITER = {}

SPEAKER_RE = re.compile(r"^[A-Z][A-Z0-9 .\-()/']{1,32}$")
RADIO_LIT = re.compile(r'^\s*([A-Z][A-Z0-9 .\-()/]{1,30}?):\s*"?(.*[a-z].*?)"?\s*$', re.S)
EXTRA_VOICES = {"PA", "INTERCEPT", "SYSTEM", "LOYALIST COMMS", "RADIO", "DISPATCH",
                "KRAP DISPATCH", "IPA", "GUARD", "OPERATOR"}
RADIO_CALLS = {"trigger_radio_chatter", "_radio"}
NOT_SPEAKERS = {"GAME", "WALK", "MENU", "PAUSED", "CUTSCENE", "MISSION1", "MISSION2",
                "MISSION3", "MISSION4", "MISSION5", "OK", "ON", "OFF", "E", "F", "R"}


def norm(t):
    return voice._norm(t or "")


def const_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                out.append(str(v.value))
            else:
                out.append("{\u2026}")
        return "".join(out)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = const_str(node.left), const_str(node.right)
        if a is not None and b is not None:
            return a + b
    return None


def mission_of(rel):
    p = rel.replace("\\", "/")
    m = re.search(r"missions/(m\d)/", p)
    if m:
        return m.group(1).upper()
    if "walking_sim" in p:
        return "M1 (walk)"
    m = re.search(r"cutscenes/(m\d)", p)
    if m:
        return m.group(1).upper() + " cutscene"
    if "route12" in p:
        return "M2 cutscene"
    if "oil_rig" in p:
        return "M1 cutscene"
    if "cutscenes/" in p:
        return "cutscene"
    if "interactions.py" in p:
        return "M1"
    return "-"


class Finder(ast.NodeVisitor):
    def __init__(self, rel):
        self.rel = rel
        self.rows = []
        self.seen = set()          # id() of string constants already claimed
        self.func = ["<module>"]
        self.ifs = []

    def visit_FunctionDef(self, node):
        self.func.append(node.name)
        self.generic_visit(node)
        self.func.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node):
        try:
            cond = ast.unparse(node.test)
        except Exception:
            cond = "?"
        self.visit(node.test)
        self.ifs.append(cond[:70])
        for n in node.body:
            self.visit(n)
        self.ifs.pop()
        self.ifs.append("not (" + cond[:60] + ")")
        for n in node.orelse:
            self.visit(n)
        self.ifs.pop()

    def _cond(self):
        c = self.func[-1]
        if self.ifs:
            c += " | " + self.ifs[-1]
        return c

    def add(self, node, channel, speaker, text, priority="", once="", strnodes=()):
        for s in strnodes:
            self.seen.add(id(s))
        self.rows.append(dict(
            file=f"{self.rel}:{node.lineno}", channel=channel, speaker=speaker,
            text=text, mission=mission_of(self.rel), condition=self._cond(),
            priority=priority, once_guard=once))

    def _channel_for(self, default):
        p = self.rel
        if "/cutscenes/" in p:
            return "cutscene"
        if "sniper3d" in p:
            return "cutscene (sniper3d)"
        if "interrog" in p:
            return "interrogation"
        if "walking_sim" in p:
            return "walk dialogue"
        return default

    def visit_Call(self, node):
        fname = (node.func.attr if isinstance(node.func, ast.Attribute)
                 else node.func.id if isinstance(node.func, ast.Name) else "")
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        if fname in RADIO_CALLS and node.args:
            text = const_str(node.args[0])
            if text is not None:
                sp, _ = voice._split_speaker(text)
                pr = kw.get("priority")
                pr = ast.unparse(pr) if pr is not None else "0"
                mark = kw.get("mark")
                if mark is None and len(node.args) >= 4:
                    mark = node.args[3]
                once = ast.unparse(mark) if mark is not None else ""
                if fname == "_radio" and once and once != "None" and pr in ("0", "None"):
                    pr = "0.5 (marked)"
                self.add(node, "radio", sp or "(none)", text, pr, once, [node.args[0]])
        elif fname not in ("get", "setdefault", "replace", "startswith", "join", "format"):
            args = node.args
            for i in range(len(args) - 1):
                sp, tx = const_str(args[i]), const_str(args[i + 1])
                if (sp and tx and SPEAKER_RE.match(sp) and sp not in NOT_SPEAKERS
                        and len(tx) >= 6 and re.search(r"[a-z]", tx)):
                    self.add(node, self._channel_for("dialogue"), sp, tx,
                             strnodes=[args[i], args[i + 1]])
                    break
        self.generic_visit(node)

    def visit_Dict(self, node):
        keys = {}
        for k, v in zip(node.keys, node.values):
            ks = const_str(k) if k is not None else None
            if ks:
                keys[ks] = v
        sp = const_str(keys["speaker"]) if "speaker" in keys else None
        tx = const_str(keys["text"]) if "text" in keys else None
        if sp is None and "name" in keys:
            sp = const_str(keys["name"])
        # NPC conversations: {"name": "OLD WOMAN", "dialogue": ["..", ".."]}
        for k, v in keys.items():
            if not (k.startswith("dialogue") or k in ("thanks", "done_dialogue")):
                continue
            if const_str(v) and k != "text":
                self.add(v, self._channel_for("npc dialogue"), sp or "(none)",
                         const_str(v), strnodes=[v])
            elif isinstance(v, (ast.List, ast.Tuple)):
                parts = [const_str(e) for e in v.elts]
                if parts and all(p is not None for p in parts):
                    self.add(v, self._channel_for("npc dialogue"), sp or "(none)",
                             "\n".join(parts), strnodes=v.elts)
        # Choice replies: "options": [(player choice, reply), ...]
        opts = keys.get("options")
        if isinstance(opts, (ast.List, ast.Tuple)):
            rsp = const_str(keys.get("reply_speaker")) if "reply_speaker" in keys else None
            for o in opts.elts:
                if isinstance(o, ast.Tuple) and len(o.elts) >= 2:
                    a, b = const_str(o.elts[0]), const_str(o.elts[1])
                    if a and b:
                        self.add(o, self._channel_for("choice reply"),
                                 rsp or "(reply)", b, strnodes=o.elts[:2])
        if sp is not None and tx and re.search(r"[A-Za-z]", tx):
            radio = keys.get("radio")
            ch = ("cutscene" if "scene" in keys or "lighting" in keys
                  else self._channel_for("dialogue"))
            if isinstance(radio, ast.Constant) and radio.value:
                ch += " (radio fx)"
            self.add(node, ch, sp or "(none)", tx,
                     strnodes=[keys["speaker"], keys["text"]])
        self.generic_visit(node)

    def visit_Tuple(self, node):
        el = node.elts
        if len(el) >= 2:
            sp, tx = const_str(el[0]), const_str(el[1])
            if (sp and tx and SPEAKER_RE.match(sp) and sp not in NOT_SPEAKERS
                    and len(tx) >= 6 and re.search(r"[a-z]", tx)):
                self.add(node, self._channel_for("dialogue"), sp, tx,
                         strnodes=[el[0], el[1]])
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str) and id(node) not in self.seen:
            m = RADIO_LIT.match(node.value)
            if m:
                self.add(node, "radio (pooled)", m.group(1).strip(), node.value)


def scan_code():
    rows = []
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(SRC).as_posix()
        if rel.startswith("audio/voice"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[audit] skip {rel}: {exc}")
            continue
        f = Finder("src/" + rel)
        f.visit(tree)
        rows.extend(f.rows)
    # Pooled 'SPEAKER: text' literals: keep only real voices (manifest
    # speakers, speakers seen in structured calls, known radio channels), so
    # HUD strings like 'TIP: press E' stay out.
    known = {s.upper() for _v, s, _t in VOICE_LINES}
    known |= {r["speaker"].upper() for r in rows if r["channel"] != "radio (pooled)"}
    known |= EXTRA_VOICES
    base = lambda s: re.sub(r"\s*\(.*?\)\s*", "", s.upper()).strip()  # noqa: E731
    known_b = {base(k) for k in known}
    return [r for r in rows if r["channel"] != "radio (pooled)"
            or base(r["speaker"]) in known_b]


# -- xlsx (stdlib) -------------------------------------------------------
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def read_xlsx(path):
    z = zipfile.ZipFile(path)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
            ss.append("".join(t.text or "" for t in si.iter("{%s}t" % _NS["m"])))
    rels = {r.get("Id"): r.get("Target")
            for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    out = {}
    for sh in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", _NS):
        tgt = rels[sh.get(_RID)]
        tgt = tgt if tgt.startswith("xl/") else "xl/" + tgt.lstrip("/")
        rows = []
        for row in ET.fromstring(z.read(tgt)).iter("{%s}row" % _NS["m"]):
            vals = {}
            for c in row.findall("m:c", _NS):
                col = re.match(r"[A-Z]+", c.get("r")).group(0)
                ci = 0
                for ch in col:
                    ci = ci * 26 + ord(ch) - 64
                v = c.find("m:v", _NS)
                if c.get("t") == "s" and v is not None:
                    val = ss[int(v.text)]
                elif c.get("t") == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter("{%s}t" % _NS["m"]))
                else:
                    val = v.text if v is not None else ""
                vals[ci - 1] = val
            if vals:
                rows.append([vals.get(i, "") for i in range(max(vals) + 1)])
        out[sh.get("name")] = rows
    return out


def sheet_rows(book, name):
    rows = book.get(name, [])
    hdr_i = next((i for i, r in enumerate(rows) if r and r[0] == "Order"), None)
    if hdr_i is None:
        return []
    hdr = rows[hdr_i]
    out = []
    for r in rows[hdr_i + 1:]:
        d = {hdr[i]: (r[i] if i < len(r) else "") for i in range(len(hdr))}
        if d.get("ID") or d.get("Exact line / dialogue"):
            out.append(d)
    return out


# -- resolve -------------------------------------------------------------
def resolve(rows):
    voice._scan_files()
    rates = []
    for r in rows:
        sp = r["speaker"] if not r["speaker"].startswith("(") else None
        vo = voice.find_line(sp, r["text"])
        r["id"] = vo or ""
        r["dur"] = 0.0
        r["notes"] = ""
        if vo and voice.has_file(vo):
            r["dur"] = voice._duration(voice._files[vo]) or 0.0
            r["audio"] = "found"
            rates.append(r["dur"] / max(1.0, voice._speech_units(r["text"])))
        elif vo:
            r["audio"] = "missing"
        else:
            r["audio"] = "unregistered"
    rate = statistics.median(rates) if rates else 0.07
    for r in rows:
        if r["audio"] == "found":
            exp = rate * voice._speech_units(r["text"])
            ratio = r["dur"] / max(0.2, exp)
            if ratio < 0.45 or ratio > 2.3:
                r["audio"] = "mismatch"
                r["notes"] += (f"clip {r['dur']:.1f}s vs ~{exp:.1f}s expected; "
                               "listen and confirm the take matches the text. ")
    return rate


def classify(r):
    ch = r["channel"]
    if ch.startswith("radio"):
        r["can_fire_in_cutscene"] = "no (radio_allowed gate)"
    elif ch.startswith("cutscene"):
        r["can_fire_in_cutscene"] = "is cutscene"
    else:
        r["can_fire_in_cutscene"] = "no (own dialogue box)"
    n = norm(r["text"])
    sp = r["speaker"].upper()
    textonly = sp in ("(NONE)", "SYSTEM", "RADIO", "HUD") or "<static>" in r["text"]
    if n in FIXED:
        r["status"] = "FIXED"
        r["notes"] += FIXED[n] + ". "
    elif n in NEEDS_WRITER:
        r["status"] = "NEEDS WRITER"
        r["notes"] += NEEDS_WRITER[n] + ". "
    elif r["audio"] == "found":
        r["status"] = "OK"
    elif r["audio"] == "mismatch" and r["id"] in BAKED_SCREAMS:
        r["status"] = "OK"
        r["audio"] = "found"
        r["notes"] = "long clip by design: death scream baked onto the line end. "
    elif r["audio"] == "mismatch":
        r["status"] = "MISSING AUDIO"
    elif textonly:
        r["status"] = "OK"
        r["notes"] += "text-only system line by design. "
    else:
        r["status"] = "MISSING AUDIO"
        r["notes"] += (f"no recording for {r['id']}. " if r["id"]
                       else "no VO id: add to VOICE_LINES, then record. ")
    if "{\u2026}" in r["text"]:
        r["notes"] += "formatted at runtime. "
    r["notes"] = r["notes"].strip()


COLS = ["id", "file", "channel", "speaker", "text", "mission", "condition",
        "priority", "audio", "duration_s", "once_guard", "can_fire_in_cutscene",
        "status", "notes"]


def _fuzzy(code_text, sheet_text):
    """Runtime-formatted line ('{…}' holes) vs the sheet's spelled-out text."""
    if "{\u2026}" not in code_text:
        return False
    pieces = [norm(p) for p in code_text.split("{\u2026}")]
    pieces = [p for p in pieces if p]
    hay, pos = norm(sheet_text), 0
    for p in pieces:
        i = hay.find(p, pos)
        if i < 0:
            return False
        pos = i + len(p)
    return bool(pieces)


def known_missing():
    """Manifest ids with no audio file on disk right now."""
    voice._scan_files()
    return sorted(v for v, _s, _t in VOICE_LINES if not voice.has_file(v))


def manifest_problems():
    """Manifest entries that neither resolve (to themselves or a documented
    duplicate) with audio nor are known-missing. Used by the smoke test."""
    from audio import voice_manifest as vm
    known = set(getattr(vm, "KNOWN_MISSING_AUDIO", ()))
    voice._scan_files()
    bad = []
    for vo, sp, tx in VOICE_LINES:
        hit = voice.find_line(sp, tx)
        if hit is None:
            bad.append((vo, "text does not resolve"))
        elif not voice.has_file(hit) and hit not in known and vo not in known:
            bad.append((vo, "no audio and not in KNOWN_MISSING_AUDIO"))
    return bad


def main():
    if "--check" in sys.argv:
        bad = manifest_problems()
        for b in bad:
            print("BAD", *b)
        print("manifest check:", "OK" if not bad else f"{len(bad)} problems")
        sys.exit(1 if bad else 0)
    if "--known-missing" in sys.argv:
        print(known_missing())
        return
    rows, seen = [], set()
    for r in scan_code():
        k = (r["file"], norm(r["text"]))
        if k in seen or not norm(r["text"]):
            continue
        seen.add(k)
        rows.append(r)
    rate = resolve(rows)
    for r in rows:
        classify(r)
        r["duration_s"] = f"{r['dur']:.2f}" if r["dur"] else ""

    by_norm = {}
    for r in rows:
        by_norm.setdefault(norm(r["text"]), []).append(r)
    used_ids = {r["id"] for r in rows if r["id"]}

    xref = []
    if XLSX.exists():
        book = read_xlsx(XLSX)
        for sheet in ("Missing lines", "Text-only review"):
            for d in sheet_rows(book, sheet):
                txt = d.get("Exact line / dialogue", "")
                sid = d.get("ID", "")
                hits = by_norm.get(norm(txt), [])
                if not hits and sid.startswith("VO_"):
                    hits = [r for r in rows if r["id"] == sid]
                if not hits:
                    hits = [r for r in rows if _fuzzy(r["text"], txt)]
                if hits:
                    h = hits[0]
                    st = h["status"]
                    where = ", ".join(x["file"] for x in hits[:3])
                    note = h["notes"]
                else:
                    st, where = "REMOVED", "-"
                    note = ("line no longer spoken anywhere in src/ (sheet said "
                            + d.get("Source file : line", "") + ")")
                xref.append(dict(sheet=sheet, sheet_id=sid,
                                 character=d.get("Character", ""),
                                 mission=d.get("Mission", ""), text=txt, status=st,
                                 audit_ids=", ".join(sorted({x["id"] for x in hits if x["id"]})),
                                 where=where, notes=note))

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: str(r.get(k, "")).replace("\n", " / ") for k in COLS})
    xc = ["sheet", "sheet_id", "character", "mission", "text", "status",
          "audit_ids", "where", "notes"]
    with open(OUT_CSV.with_name("voice_audit_xlsx.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w2 = csv.DictWriter(fh, fieldnames=xc)
        w2.writeheader()
        for x in xref:
            w2.writerow({k: str(x[k]).replace("\n", " / ") for k in xc})

    def cell(s):
        return str(s).replace("|", "\\|").replace("\n", " / ")

    counts, xcounts = {}, {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    for x in xref:
        xcounts[x["status"]] = xcounts.get(x["status"], 0) + 1
    unused = [v for v, _s, _t in VOICE_LINES if v not in used_ids]
    km = known_missing()
    fmt = lambda c: ", ".join(f"{k} {v}" for k, v in sorted(c.items()))  # noqa: E731
    L = ["# Voice-line audit", "",
         "Generated by `python tools/voice_audit.py`; do not hand-edit.", "",
         f"- Spoken lines found in code: **{len(rows)}** ({fmt(counts)})",
         f"- Manifest entries: {len(VOICE_LINES)}; audio on disk: "
         f"{len(VOICE_LINES) - len(km)}; known missing: {len(km)}",
         f"- Manifest entries not referenced by any scanned line: {len(unused)}",
         f"- Median speaking rate used for the mismatch check: {rate:.3f} s/unit",
         "- Radio lines cannot fire in cutscenes: `core.interactions.radio_allowed()` "
         "gates the pump (priority > 0 held, priority 0 dropped).", ""]
    if xref:
        L += ["## Spreadsheet cross-reference (Missing_voice_lines_by_character.xlsx)", "",
              f"{len(xref)} rows ({fmt(xcounts)}). CSV: `validation/voice_audit_xlsx.csv`.", "",
              "| Sheet | ID | Character | M | Line | Status | Resolves to | Where | Notes |",
              "|---|---|---|---|---|---|---|---|---|"]
        for x in xref:
            L.append("| " + " | ".join(cell(x[k]) for k in xc) + " |")
        L.append("")
    L += ["## All spoken lines", "",
          "| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS)]
    for r in rows:
        L.append("| " + " | ".join(cell(r.get(k, "")) for k in COLS) + " |")
    L += ["", "## Manifest entries not referenced by scanned code", "",
          "Usually lines assembled at runtime, or retired.", ""]
    for v, s, t in VOICE_LINES:
        if v in unused:
            L.append(f"- {v} {s}: {cell(t)[:110]}" + (" (no audio)" if v in km else ""))
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"[audit] {len(rows)} lines ({fmt(counts)}) | xlsx {len(xref)} rows "
          f"({fmt(xcounts)}) | unused manifest {len(unused)} | known missing {len(km)}")


if __name__ == "__main__":
    main()
