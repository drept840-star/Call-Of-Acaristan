"""Procedural-art inventory (Polish Task 7, step 1).

Scans ``src/`` with ``ast`` for procedural drawing - ``pygame.draw.*``,
``gfxdraw.*`` and polygon/surface building - per function, groups the
functions into visual asset families, and ranks the families by
``visual impact x frequency on screen``. A function counts as
*sprite-backed* when it consults the loaded-art tier (``artpack``,
``sprite_lib``, ``art_cache``, the M5 sprite bake) before drawing, i.e. the
procedural code in it is only the fallback.

    python tools/sprites/inventory.py            # writes validation/sprite_inventory.md
    python tools/sprites/inventory.py --json     # also dumps validation/sprite_inventory.json

Deterministic: same tree -> same report.
"""
import ast
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "src")
OUT_MD = os.path.join(ROOT, "validation", "sprite_inventory.md")
OUT_JSON = os.path.join(ROOT, "validation", "sprite_inventory.json")

# Families in brief order; (key, title, impact weight, name/path regex).
# First match wins, so the specific families come before the broad ones.
FAMILIES = [
    ("bodies", "Player / NPC / enemy bodies", 5.0,
     r"player|enemy|guard|soldier|npc|body|figure|humanoid|person|civil|hostage|walker|_man\b|"
     r"maru|vasile|biribel|sniper|ucilev|actor|crowd|silhouette|corpse|portrait_body"),
    ("weapons_fx", "Weapons & muzzle FX", 4.0,
     r"weapon|rifle|gun|muzzle|bullet|tracer|shell|casing|grenade|molotov|explos|blast|"
     r"flash|spark|smoke|fire|flame|impact|shot\b|scope"),
    ("props", "Environment props", 3.0,
     r"crate|barrel|vehicle|car|truck|van|tank|jeep|tram|furniture|desk|table|chair|bed|"
     r"terminal|computer|monitor|crt|shelf|locker|cabinet|door|prop|press|machine|server|"
     r"rack|lamp|light_pole|bench|sandbag|barricade|fence|gate|boat|ship|crane|pipe"),
    ("tiles", "Floor / wall tiles & trims", 2.5,
     r"tile|floor|wall|ground|road|street|grass|water|terrain|trim|room|corridor|map\b|"
     r"background|bg\b|level|world|static"),
    ("decals", "Decals (posters, graffiti, blood, scorch)", 2.0,
     r"poster|graffit|blood|scorch|decal|stain|sign|banner|flag|crest|paper|note|leaflet"),
    ("ui", "UI icons / portraits / HUD", 2.0,
     r"icon|portrait|hud|ui\b|button|panel|menu|radio|minimap|cursor|bar\b|meter|badge|"
     r"objective|prompt|dialog|subtitle|inventory"),
    ("cutscene", "Cutscene props / backdrops", 1.0, r"cutscene|scene|backdrop|sky|cloud|skyline"),
]
_FAM_RE = [(k, t, w, re.compile(rx, re.I)) for k, t, w, rx in FAMILIES]

# On-screen frequency by where the code lives: gameplay draws every frame.
def _frequency(rel):
    r = rel.replace("\\", "/")
    if r.startswith("entities/") or re.match(r"missions/m\d/draw\.py", r) or \
            r.startswith(("missions/walking_sim", "world/", "core/staticlayer")):
        return 3.0
    if r.startswith("missions/"):
        return 2.0
    if r.startswith(("ui/", "core/hud")):
        return 2.0
    if r.startswith("cutscenes/"):
        return 1.0
    return 1.5


SPRITE_HINTS = re.compile(r"artpack\.|sprite_lib\.|art_cache\.|_decal\.add|m5_sprite|"
                          r"load_sprite|get_sprite|sprites\.get|bake_m5|art\.m5")
_DRAW_ATTRS = {"rect", "circle", "ellipse", "line", "lines", "aaline", "aalines", "polygon",
               "arc", "pie", "filled_polygon", "filled_circle", "aacircle", "aapolygon",
               "box", "hline", "vline", "pixel", "filled_ellipse", "aaellipse", "trigon",
               "filled_trigon", "bezier", "textured_polygon"}


def _is_draw(call):
    f = call.func
    if not isinstance(f, ast.Attribute) or f.attr not in _DRAW_ATTRS:
        return False
    v = f.value
    if isinstance(v, ast.Attribute) and v.attr in ("draw", "gfxdraw"):
        return True
    return isinstance(v, ast.Name) and v.id in ("draw", "gfxdraw", "pgd", "gfx")


def _family(rel, name):
    hay = name + " " + rel
    for key, _t, _w, rx in _FAM_RE:
        if rx.search(name):
            return key
    for key, _t, _w, rx in _FAM_RE:
        if rx.search(hay):
            return key
    return "misc"


def scan():
    rows = []
    for dp, dns, fns in os.walk(SRC):
        dns[:] = sorted(d for d in dns if d != "__pycache__")
        for fn in sorted(fns):
            if not fn.endswith(".py"):
                continue
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, SRC).replace("\\", "/")
            src = open(p, encoding="utf-8", errors="replace").read()
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            lines = src.splitlines()
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                n = sum(1 for c in ast.walk(node) if isinstance(c, ast.Call) and _is_draw(c))
                if not n:
                    continue
                body = "\n".join(lines[node.lineno - 1:getattr(node, "end_lineno", node.lineno)])
                rows.append(dict(file=rel, func=node.name, line=node.lineno, calls=n,
                                 family=_family(rel, node.name), freq=_frequency(rel),
                                 sprite=bool(SPRITE_HINTS.search(body)),
                                 baked=rel.startswith("art/")))
    # nested functions are counted inside their parent too: keep innermost only
    rows.sort(key=lambda r: (r["file"], r["line"]))
    return rows


def rank(rows):
    w = {k: wt for k, _t, wt, _r in FAMILIES}
    w["misc"] = 1.0
    fams = {}
    for r in rows:
        score = r["calls"] * r["freq"] * w[r["family"]]
        f = fams.setdefault(r["family"], dict(score=0.0, sprite=0.0, calls=0, funcs=0, files={}))
        f["score"] += score
        f["calls"] += r["calls"]
        f["funcs"] += 1
        f["files"][r["file"]] = f["files"].get(r["file"], 0) + r["calls"]
        if r["sprite"] or r["baked"]:
            f["sprite"] += score
    return fams


def report(rows, fams, status):
    titles = {k: t for k, t, _w, _r in FAMILIES}
    titles["misc"] = "Uncategorised"
    total = sum(f["score"] for f in fams.values()) or 1.0
    backed = sum(f["sprite"] for f in fams.values())
    out = ["# Sprite inventory (Polish Task 7)", "",
           "Generated by `python tools/sprites/inventory.py` - do not hand-edit the tables.", "",
           "Weight = draw calls x on-screen frequency (gameplay 3, mission/UI 2, other 1.5,",
           "cutscene 1) x family impact (bodies 5, weapons/FX 4, props 3, tiles 2.5,",
           "decals/UI 2, cutscene/misc 1). *Sprite-backed* = the function consults the",
           "loaded-art tier first and only falls back to its procedural code.", "",
           "**Sprite-backed share of weighted procedural art: {:.1f}%** ({} functions, {} draw calls scanned)"
           .format(100.0 * backed / total, len(rows), sum(r["calls"] for r in rows)), "",
           "## Families, ranked", "",
           "| # | Family | Weighted | Share | Sprite-backed | Draw calls | Functions | Target status |",
           "|---|---|---|---|---|---|---|---|"]
    order = sorted(fams.items(), key=lambda kv: -kv[1]["score"])
    for i, (k, f) in enumerate(order, 1):
        out.append("| {} | {} | {:.0f} | {:.1f}% | {:.0f}% | {} | {} | {} |".format(
            i, titles[k], f["score"], 100 * f["score"] / total,
            100 * f["sprite"] / (f["score"] or 1), f["calls"], f["funcs"], status.get(k, "-")))
    out += ["", "## Heaviest files per family", ""]
    for k, f in order:
        top = sorted(f["files"].items(), key=lambda kv: -kv[1])[:6]
        out.append("- **{}**: ".format(titles[k]) + ", ".join("`{}` ({})".format(a, b) for a, b in top))
    out += ["", "## Top 40 functions by weight", "",
            "| Function | File:line | Family | Calls | Weight | Sprite-backed |", "|---|---|---|---|---|---|"]
    w = {k: wt for k, _t, wt, _r in FAMILIES}
    w["misc"] = 1.0
    for r in sorted(rows, key=lambda r: -r["calls"] * r["freq"] * w[r["family"]])[:40]:
        out.append("| `{}` | `{}:{}` | {} | {} | {:.0f} | {} |".format(
            r["func"], r["file"], r["line"], r["family"], r["calls"],
            r["calls"] * r["freq"] * w[r["family"]], "yes" if (r["sprite"] or r["baked"]) else "no"))
    return "\n".join(out) + "\n", 100.0 * backed / total


def load_status():
    p = os.path.join(os.path.dirname(__file__), "status.json")
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main(argv):
    rows = scan()
    status = load_status()
    # status.json: {"families": {family: target status}, "fallbacks":
    # {file: [func, ...]}}. A listed func is a procedural renderer that only
    # runs when its caller's sprite lookup misses (the caller holds the
    # artpack call, so the body scan above cannot see it).
    fallbacks = status.get("fallbacks", {})
    for r in rows:
        if r["func"] in fallbacks.get(r["file"], ()):
            r["sprite"] = True
    fams = rank(rows)
    md, pct = report(rows, fams, status.get("families", status))
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(md)
    if "--json" in argv:
        with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(dict(rows=rows, families=fams), fh, indent=1, sort_keys=True)
    print("inventory: {} functions, sprite-backed {:.1f}% -> {}".format(
        len(rows), pct, os.path.relpath(OUT_MD, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
