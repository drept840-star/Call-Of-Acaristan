"""Keep the generated parts of docs/ARCHITECTURE_MAP.md and docs/FILE_INDEX.md in sync.

    python tools/sync_arch_map.py           # rewrite both files if out of date
    python tools/sync_arch_map.py --check   # exit 1 if either is out of date (pre-commit, smoke)
    python tools/sync_arch_map.py --dump-sigs   # print the AST signature block only

Generated into ARCHITECTURE_MAP.md (deterministic, LF, UTF-8 no BOM):
  s1    the `states:` line in section 1 and the section 9.3 FSM table (AST of src/app.py:
        every `class _X(GameState)` with `name = "NAME"`). Existing role text is kept.
  s2.1  AST-verified signatures between <!-- AUTO:sigs --> markers (SIG_SPECS below).
        The hand-written coordinate/pose contracts around it are NOT touched.
  s8.1b GLB geometry between <!-- AUTO:glb --> markers (tris, size, AABB, materials).
  s8.2  the `M/` mesh inventory rows. Existing `source` / `used by` text is kept; new
        files get an auto row; callers are grepped from src/ and rendered as `(auto: ...)`.
  s20.1 monolith anchors: banner comments, classes and long gaps for ANCHOR_FILES.

Generated into FILE_INDEX.md (the cold catalogs, kept out of every-prompt context):
  s12.1 DEV_JUMPS table (core/dev_jumps.py).
  s20   per-file rows (line counts, new/removed files). Existing descriptions are kept.
  s21   tools/ docstring index; s22 tests/ index (hand-written, carried over verbatim).

Section 8.1 (the `A/` table) belongs to tools/map_assets3d.py; this tool never edits it.
Run by .githooks/pre-commit.
"""
import ast
import json
import os
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "docs" / "ARCHITECTURE_MAP.md"
INDEX = ROOT / "docs" / "FILE_INDEX.md"
SRC = ROOT / "src"

# --------------------------------------------------------------------- specs
# (path, extra private names to show, {class: [methods] or None for all public},
#  names to hide). Public = no leading underscore.
SIG_SPECS = [
    ("src/engine3d/core.py", (), {"Renderer": [], "SoftwareRenderer": None, "Mesh": None,
                                  "Light": None, "Obj": None},
     ("lerp", "clamp", "smooth", "ease_in_out", "ease_out", "ease_in", "mix_col",
      "v_add", "v_sub", "v_mul", "v_dot", "v_len", "v_norm", "v_lerp")),
    ("src/engine3d/gl.py", (), {"GLRenderer": None}, ()),
    ("src/engine3d/rig.py", (), {"Humanoid": None}, ()),
    ("src/engine3d/ik.py", (), {}, ()),
    ("src/engine3d/hold.py", (), {}, ()),
    ("src/engine3d/textures.py", (), {"Tex": None}, ()),
    ("src/cutscenes/m6world3d.py", ("_t",), {}, ()),
    ("src/game/render3d_bridge.py", (), {}, ()),
    ("src/game/scenery3d.py", (), {}, ()),
]
# m7world3d / m5fx3d / m6fx3d / chase_set / the mesh importers are mission-file-local:
# their signatures live in docs/FILE_INDEX.md's source-file rows, not in every prompt.
# Data tables whose KEYS an external reader needs (name in module -> label)
KEY_TABLES = [
    ("src/engine3d/rig.py", ["NEUTRAL", "POSES", "EXPRESSIONS", "SLOTS"]),
    ("src/engine3d/hold.py", ["GRIPS", "MODES", "POLES"]),
    ("src/cutscenes/m6world3d.py", ["LOOKS", "BIRI", "LAST"]),
    ("src/cutscenes/m7world3d.py", ["LOOKS"]),
    ("src/game/render3d_bridge.py", ["MESHES_DIR", "SETS_DIR", "PRESETS_DIR", "TEXTURES_DIR"]),
]
ANCHOR_FILES = ["src/app.py", "src/cutscenes/m6world3d.py", "src/cutscenes/m7world3d.py",
                "src/missions/m8/revenge/chase_set.py", "src/missions/m2/draw.py",
                "src/missions/m3/draw.py", "src/audio/audio.py", "src/ui/match_screen.py"]
ANCHOR_GAP = 400   # a top-level def this far from the last anchor becomes one
SKIP_DIRS = {"__pycache__", ".venv", "build", "dist"}


def read(p):
    return Path(p).read_text(encoding="utf-8", errors="replace")


def parse(rel):
    return ast.parse(read(ROOT / rel))


def nlines(rel):
    return len(read(ROOT / rel).splitlines())


# ------------------------------------------------------------ AST signatures
def _unp(n):
    try:
        return ast.unparse(n)
    except Exception:
        return "?"


def _ret(fn):
    if fn.returns is not None:
        return " -> " + _unp(fn.returns)
    rets, stack = [], list(fn.body)
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(n, ast.Return) and n.value is not None:
            rets.append(n.value)
        stack.extend(ast.iter_child_nodes(n))
    if not rets:
        return ""
    kinds = set()
    for v in rets:
        if isinstance(v, ast.Tuple):
            kinds.add("tuple%d" % len(v.elts))
        elif isinstance(v, ast.Call) and isinstance(v.func, (ast.Name, ast.Attribute)):
            nm = v.func.id if isinstance(v.func, ast.Name) else v.func.attr
            if nm[:1].isupper():
                kinds.add(nm)
        elif isinstance(v, ast.List):
            kinds.add("list")
        elif isinstance(v, ast.Dict):
            kinds.add("dict")
        elif isinstance(v, ast.Constant) and isinstance(v.value, (bool, str)):
            kinds.add(type(v.value).__name__)
    return " -> ~" + "|".join(sorted(kinds)) if len(kinds) == 1 or (kinds and len(kinds) <= 2) else ""


def _sig(fn, indent=""):
    args = _unp(fn.args)
    line = "%sdef %s(%s)%s" % (indent, fn.name, args, _ret(fn))
    if len(line) > 170:
        line = line[:167] + "..."
    doc = ast.get_docstring(fn)
    if doc:
        first = re.split(r"(?<=[.:])\s|\n", doc.strip(), maxsplit=1)[0].strip()
        first = first.rstrip(":.")
        if first and len(line) < 92 and len(first) <= 52:
            line += "  # " + first
    return line


def _is_public(name):
    return not name.startswith("_")


def sig_block(rel, extra, classes, hide):
    tree = parse(rel)
    lines = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (_is_public(n.name) or n.name in extra) and n.name not in hide:
                lines.append(_sig(n))
        elif isinstance(n, ast.ClassDef):
            if not (_is_public(n.name) or n.name in extra):
                continue
            bases = ",".join(_unp(b) for b in n.bases)
            lines.append("class %s%s" % (n.name, "(%s)" % bases if bases else ""))
            want = classes.get(n.name, None)
            if n.name not in classes and classes:
                want = []     # classes not listed: header only when a filter exists
            for m in n.body:
                if isinstance(m, ast.FunctionDef) and (_is_public(m.name) or m.name == "__init__"):
                    if want is None or m.name in want or m.name == "__init__":
                        lines.append(_sig(m, "    "))
            if n.name == "Renderer" and want == []:
                lines.append("    # alias of GLRenderer when moderngl is present else SoftwareRenderer (see gl.py)")
    return lines


def key_tables(rel, names):
    tree = parse(rel)
    out = []
    for n in tree.body:
        tgt = None
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            tgt = n.targets[0].id
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            tgt = n.target.id
        if tgt not in names:
            continue
        val = n.value
        if isinstance(val, ast.Dict):
            ks = []
            for k in val.keys:
                ks.append(_unp(k) if k is not None else "**")
            out.append("%s keys: %s" % (tgt, " ".join(k.strip("'\"") for k in ks)))
        elif isinstance(val, ast.Call) and isinstance(val.func, ast.Name) and val.func.id == "dict":
            out.append("%s keys: %s" % (tgt, " ".join(k.arg for k in val.keywords if k.arg)))
        else:
            txt = _unp(val)
            out.append("%s = %s" % (tgt, txt if len(txt) <= 200 else txt[:197] + "..."))
    return out


def pose_details(rel="src/engine3d/rig.py"):
    """POSES name -> keys it sets (so sign rules are checkable per pose)."""
    tree = parse(rel)
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "POSES":
            res = []
            for k, v in zip(n.value.keys, n.value.values):
                if isinstance(v, ast.Call) and isinstance(k, ast.Constant):
                    res.append(str(k.value))
            return res
    return []


def build_sigs():
    out = []
    for rel, extra, classes, hide in SIG_SPECS:
        out.append("**`%s`** (%d lines)" % (rel.replace("src/", "", 1) if rel.startswith("src/") else rel,
                                            nlines(rel)))
        out.append("```")
        out.extend(sig_block(rel, extra, classes, hide))
        for r, names in KEY_TABLES:
            if r == rel:
                out.extend(key_tables(r, names))
        if rel.endswith("engine3d/textures.py"):
            names = sorted(f.stem for f in (ROOT / "assets" / "tex3d").glob("*.png"))
            out.append("tex names (assets/tex3d): " + " ".join(names))
        out.append("```")
    out.append("Signature notation: `-> ~T` = return type inferred from the `return` statements (no annotation in source); `# text` = first docstring sentence.")
    return "\n".join(out)


# ------------------------------------------------------------------- markers
def _marker_re(tag):
    return re.compile(r"(<!-- AUTO:%s[^>]*-->\n)(.*?)(<!-- /AUTO:%s -->)" % (tag, tag), re.S)


def replace_marked(text, tag, body):
    rx = _marker_re(tag)
    if not rx.search(text):
        return text
    return rx.sub(lambda m: m.group(1) + body.rstrip("\n") + "\n" + m.group(3), text, 1)


# ----------------------------------------------------------------------- FSM
def fsm_states():
    tree = parse("src/app.py")
    res = []
    for n in tree.body:
        if isinstance(n, ast.ClassDef) and any(_unp(b).endswith("GameState") for b in n.bases):
            nm = None
            for s in n.body:
                if isinstance(s, ast.Assign) and isinstance(s.targets[0], ast.Name) and s.targets[0].id == "name" \
                        and isinstance(s.value, ast.Constant):
                    nm = s.value.value
            if nm:
                doc = (ast.get_docstring(n) or "").strip().split("\n")[0]
                res.append((nm, n.name, doc))
    return res


def sync_fsm(text):
    states = fsm_states()
    # section 1 `states:` line
    names = " ".join(c for _, c, _ in states)
    wrapped, cur = [], ""
    for w in names.split():
        if len(cur) + len(w) + 1 > 78:
            wrapped.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    wrapped.append(cur)
    pad = " " * 10
    block = "GameStateManager (core/fsm.py) states: " + wrapped[0] + "".join("\n" + pad + w for w in wrapped[1:])
    text = re.sub(r"GameStateManager \(core/fsm\.py\) states: .*?(?=\n    _GameState_\.update)",
                  lambda m: block, text, count=1, flags=re.S)
    # section 9.3 table
    hdr = "| `name` | class | role |\n|---|---|---|\n"
    i = text.find(hdr)
    if i < 0:
        return text
    i += len(hdr)
    rows = {}
    j = i
    for ln in text[i:].split("\n"):
        m = re.match(r"^\| `(\w+)` \| `(\w+)` \| (.*) \|$", ln)
        if not m:
            break
        rows[m.group(1)] = m.group(3)
        j += len(ln) + 1
    new = []
    for nm, cls, doc in states:
        role = rows.get(nm) or (doc.rstrip(".") + " (auto)" if doc else "(auto: add role)")
        new.append("| `%s` | `%s` | %s |" % (nm, cls, role))
    return text[:i] + "\n".join(new) + "\n" + text[j:]


# ------------------------------------------------------------------ GLB specs
_CT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def _glb(path):
    data = path.read_bytes()
    if data[:4] != b"glTF":
        return None
    ln = struct.unpack_from("<I", data, 12)[0]
    js = json.loads(data[20:20 + ln])
    return js


def glb_info(path):
    try:
        js = _glb(path)
    except Exception:
        return None
    if js is None:
        return None
    acc = js.get("accessors", [])
    meshes = js.get("meshes", [])
    mats = js.get("materials", [])
    tris = 0
    prims = 0
    for m in meshes:
        for p in m.get("primitives", []):
            if p.get("mode", 4) not in (4, 5, 6):
                continue
            prims += 1
            if "indices" in p:
                tris += acc[p["indices"]]["count"] // 3
            elif "POSITION" in p.get("attributes", {}):
                tris += acc[p["attributes"]["POSITION"]]["count"] // 3
    # world AABB: walk node tree with TRS/matrix, transform accessor min/max corners
    nodes = js.get("nodes", [])

    def mat_of(n):
        if "matrix" in n:
            m = n["matrix"]
            return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
        t = n.get("translation", [0, 0, 0])
        q = n.get("rotation", [0, 0, 0, 1])
        s = n.get("scale", [1, 1, 1])
        x, y, z, w = q
        r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
             [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
             [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
        return [[r[0][0] * s[0], r[0][1] * s[1], r[0][2] * s[2], t[0]],
                [r[1][0] * s[0], r[1][1] * s[1], r[1][2] * s[2], t[1]],
                [r[2][0] * s[0], r[2][1] * s[1], r[2][2] * s[2], t[2]],
                [0, 0, 0, 1]]

    def mul(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

    lo = [1e18] * 3
    hi = [-1e18] * 3

    def visit(idx, parent):
        n = nodes[idx]
        m = mul(parent, mat_of(n))
        if "mesh" in n:
            for p in meshes[n["mesh"]].get("primitives", []):
                pa = acc[p["attributes"]["POSITION"]] if "POSITION" in p.get("attributes", {}) else None
                if not pa or "min" not in pa or "max" not in pa:
                    continue
                for cx in (pa["min"][0], pa["max"][0]):
                    for cy in (pa["min"][1], pa["max"][1]):
                        for cz in (pa["min"][2], pa["max"][2]):
                            for a in range(3):
                                v = m[a][0] * cx + m[a][1] * cy + m[a][2] * cz + m[a][3]
                                lo[a] = min(lo[a], v)
                                hi[a] = max(hi[a], v)
        for c in n.get("children", []):
            visit(c, m)

    ident = [[1 if i == j else 0 for j in range(4)] for i in range(4)]
    scene = js.get("scenes", [{}])[js.get("scene", 0)] if js.get("scenes") else {}
    roots = scene.get("nodes", list(range(len(nodes))))
    try:
        for r in roots:
            visit(r, ident)
    except Exception:
        pass
    if lo[0] > hi[0]:
        return dict(tris=tris, prims=prims, mats=mats, nodes=len(nodes), skins=len(js.get("skins", [])),
                    anims=len(js.get("animations", [])), aabb=None)
    return dict(tris=tris, prims=prims, mats=mats, nodes=len(nodes), skins=len(js.get("skins", [])),
                anims=len(js.get("animations", [])), aabb=(lo, hi))


def _srgb(v):
    v = max(0.0, min(1.0, v))
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def _col(m):
    pbr = m.get("pbrMetallicRoughness", {})
    c = pbr.get("baseColorFactor")
    tex = "tex" if "baseColorTexture" in pbr else ""
    if c:
        h = "#%02x%02x%02x" % tuple(int(round(_srgb(v) * 255)) for v in c[:3])
        return h + ("+tex" if tex else "")
    return tex or "-"


def glb_rows():
    base = ROOT / "assets" / "3D"
    rows = []
    for p in sorted(base.rglob("*.glb")):
        info = glb_info(p)
        rel = p.relative_to(base).as_posix()
        if not info:
            rows.append("| `%s` | unreadable | | | |" % rel)
            continue
        ab = info["aabb"]
        if ab:
            lo, hi = ab
            size = "%.2fx%.2fx%.2f" % tuple(hi[i] - lo[i] for i in range(3))
            ctr = "%.2f,%.2f,%.2f" % tuple((hi[i] + lo[i]) / 2 for i in range(3))
            gy = "%.2f" % lo[1]
        else:
            size = ctr = gy = "?"
        mats = ", ".join("%s %s" % (m.get("name", "mat%d" % i), _col(m))
                         for i, m in enumerate(info["mats"][:6]))
        if len(info["mats"]) > 6:
            mats += " (+%d)" % (len(info["mats"]) - 6)
        extra = ""
        if info["skins"] or info["anims"]:
            extra = " skins=%d anims=%d" % (info["skins"], info["anims"])
        rows.append("| `%s` | %d | %s | %s | %s | %s%s |" % (rel, info["tris"], size, ctr, gy, mats or "-", extra))
    head = ("| `A/` glb | tris | size WxHxD m | AABB centre x,y,z | min y | materials (name base colour) |\n"
            "|---|---|---|---|---|---|")
    return head + "\n" + "\n".join(rows) + (
        "\n\nAABB is in glTF space (Y up, +Z toward the viewer, right-handed) after node transforms, before any "
        "importer re-axis; `min y` is the grounding offset (0 = sits on y=0). Importers (`T/ae_import_*`) re-axis to engine3d (left-handed, +Z forward).")


# --------------------------------------------------------------- meshes (8.2)
def _src_files():
    out = {}
    for p in SRC.rglob("*.py"):
        if SKIP_DIRS & set(p.parts):
            continue
        out[p.relative_to(SRC).as_posix()] = read(p)
    return out


ROW82 = re.compile(r"^\| `([^`]+)` \| (.*?) \| (.*) \|$")


def sync_meshes(text):
    hdr = "| `M/` file | source | used by |\n|---|---|---|\n"
    i = text.find(hdr)
    if i < 0:
        return text
    i += len(hdr)
    old, j = {}, i
    for ln in text[i:].split("\n"):
        m = ROW82.match(ln)
        if not m:
            break
        old[m.group(1)] = (m.group(2), m.group(3))
        j += len(ln) + 1
    mdir = SRC / "game" / "content" / "meshes"
    files = sorted(p.name for p in mdir.iterdir() if p.name.endswith((".mesh.json", ".rig.json")))
    srcs = None
    rows = []
    for f in files:
        if f in old:
            src, used = old[f]
            rows.append("| `%s` | %s | %s |" % (f, src, used))
            continue
        srcs = srcs or _src_files()
        stem = f.split(".")[0]
        keys = ('"%s"' % stem, "'%s'" % stem)
        refs = sorted(p for p, s in srcs.items() if any(k in s for k in keys))
        used = ", ".join("`%s`" % r.replace("missions/", "", 1) for r in refs[:6]) or "unreferenced"
        rows.append("| `%s` | ? (auto) | %s (auto) |" % (f, used))
    return text[:i] + "\n".join(rows) + "\n" + text[j:]


# ------------------------------------------------------------------ dev jumps
def dev_jump_block():
    ns = {}
    exec(compile(read(SRC / "core" / "dev_jumps.py"), "dev_jumps.py", "exec"), ns)
    tab = ns["DEV_JUMPS"]
    out = ["| target | flag | what |", "|---|---|---|"]
    for k, (flag, desc) in tab.items():
        out.append("| `%s` | `%s` | %s |" % (k, flag, desc.replace("|", "/")))
    return "\n".join(out)


# ------------------------------------------------------------ s20 file index
S20_HEAD = "## 20. Every source file"
ENTRY = re.compile(r"^- `([^`]+)` (\d+)( - .*)?$")


def _doc1(path):
    try:
        t = ast.parse(read(path))
    except SyntaxError:
        return "(syntax error)"
    d = ast.get_docstring(t)
    if d:
        first = d.strip().split("\n\n")[0].replace("\n", " ")
        m = re.match(r"(.+?[.!?])(\s|$)", first)
        first = (m.group(1) if m else first).strip()
        return first if len(first) <= 130 else first[:127] + "..."
    pub = [n.name for n in t.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_")]
    return "Public: " + ", ".join("`%s`" % p for p in pub[:8]) if pub else "(no docstring)"


def sync_s20(text):
    a = text.find(S20_HEAD)
    b = text.find("\n## 21.")
    if a < 0 or b < 0:
        return text
    body = text[a:b]
    lines = body.split("\n")
    # parse existing sections
    sec_order, secs, pre = [], {}, []
    cur = None
    for ln in lines:
        m = re.match(r"^\*\*`(src/[^`]*)`\*\*$", ln)
        if m:
            cur = m.group(1)
            sec_order.append(cur)
            secs[cur] = []
            continue
        if cur is None:
            pre.append(ln)
        else:
            secs[cur].append(ln)
    disk = {}
    for p in SRC.rglob("*.py"):
        if SKIP_DIRS & set(p.parts):
            continue
        d = "src/" + p.parent.relative_to(SRC).as_posix() + "/" if p.parent != SRC else "src/"
        d = d.replace("src/./", "src/")
        disk.setdefault(d, []).append(p)
    out = list(pre)
    while out and out[-1] == "":
        out.pop()
    for d in sorted(set(sec_order) | set(disk), key=lambda s: s):
        files = {p.name: p for p in disk.get(d, [])}
        old_lines = secs.get(d, [])
        kept, seen = [], set()
        for ln in old_lines:
            m = ENTRY.match(ln)
            if m:
                name = m.group(1)
                if name in files:
                    seen.add(name)
                    n = nlines(files[name].relative_to(ROOT))
                    kept.append("- `%s` %d%s" % (name, n, m.group(3) or ""))
                continue           # entries for deleted files are dropped
            if ln.strip():
                # free-form note lines (e.g. the m5 stale-copy note): keep only if its files still exist
                kept.append(ln)
        covered = " ".join(kept)
        for name in sorted(files):
            if name in seen:
                continue
            if "stale tracked copies" in covered and d == "src/art/m5/":
                continue
            n = nlines(files[name].relative_to(ROOT))
            kept.append("- `%s` %d - %s (auto)" % (name, n, _doc1(files[name])))
        # stable order: entries by name, notes stay last
        ents = sorted((l for l in kept if ENTRY.match(l)), key=lambda l: ENTRY.match(l).group(1))
        notes = [l for l in kept if not ENTRY.match(l)]
        if not ents and not notes:
            continue
        out.append("")
        out.append("**`%s`**" % d)
        out.append("")
        out.extend(ents)
        out.extend(notes)
    return text[:a] + "\n".join(out) + "\n" + text[b:]


# ---------------------------------------------------------------- anchors 20.1
BANNER = re.compile(r"^# ?[─\-=#*]{2,}\s*(.*?)\s*[─\-=#*]*\s*$")


def anchors(rel):
    src = read(ROOT / rel)
    lines = src.splitlines()
    total = len(lines)
    tree = ast.parse(src)
    pts = {}
    for i, ln in enumerate(lines, 1):
        m = BANNER.match(ln)
        if m and re.search(r"[A-Za-z]{3}", m.group(1)):
            pts.setdefault(i, m.group(1)[:48])
    defs = []
    for n in tree.body:
        if isinstance(n, ast.ClassDef):
            pts.setdefault(n.lineno, "class " + n.name)
        if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            defs.append((n.lineno, n.name))
    last = 1
    for ln in sorted(set(pts) | {d for d, _ in defs}):
        if ln in pts:
            last = ln
        elif ln - last >= ANCHOR_GAP:
            pts[ln] = "def " + dict(defs)[ln]
            last = ln
    starts = sorted(pts)
    if not starts or starts[0] > 40:
        starts.insert(0, 1)
        pts[1] = "header/imports"
    out = []
    for k, s in enumerate(starts):
        e = starts[k + 1] - 1 if k + 1 < len(starts) else total
        out.append("%d-%d %s" % (s, e, pts[s]))
    return total, out


def anchor_block():
    out = ["Line ranges (generated) for the monoliths; give `tools/ai_bundle.py path:start-end` the slice you need.", ""]
    for rel in ANCHOR_FILES:
        total, parts = anchors(rel)
        out.append("- `%s` (%d): %s" % (rel.replace("src/", "", 1), total, "; ".join(parts)))
    return "\n".join(out)


# ------------------------------------------------------------------- driver
def sync_map(text):
    text = sync_fsm(text)
    text = replace_marked(text, "sigs", build_sigs())
    text = replace_marked(text, "glb", glb_rows())
    text = sync_meshes(text)
    text = replace_marked(text, "anchors", anchor_block())
    return text


def sync_index(text):
    text = replace_marked(text, "devjumps", dev_jump_block())
    text = sync_s20(text)
    return text


def _read(path):
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n") if path.exists() else ""


def main():
    if "--dump-sigs" in sys.argv:
        sys.stdout.reconfigure(encoding="utf-8")
        print(build_sigs())
        return 0
    cur_map, cur_idx = _read(MAP), _read(INDEX)
    new_map, new_idx = sync_map(cur_map), sync_index(cur_idx)
    ok = (new_map == cur_map and new_idx == cur_idx
          and b"\r\n" not in MAP.read_bytes()
          and (not INDEX.exists() or b"\r\n" not in INDEX.read_bytes()))
    if "--check" in sys.argv:
        print("SYNC ARCH MAP: OK" if ok else "SYNC ARCH MAP: STALE - run python tools/sync_arch_map.py")
        return 0 if ok else 1
    if ok:
        print("SYNC ARCH MAP: OK")
        return 0
    with open(MAP, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new_map)
    with open(INDEX, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new_idx)
    print("SYNC ARCH MAP: updated docs/ARCHITECTURE_MAP.md + docs/FILE_INDEX.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
