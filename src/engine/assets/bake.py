"""Deterministic bake + content hashing + lint for rendered assets (§6.5).

Bake output per pack: ``<root>/<baked_dir>/<name>_<variant>.png`` and
``<baked_dir>/.bakeinfo.json``::

    {"schema": "ae.bakeinfo/1", "pack": "m5", "tool": "ae_bake/1",
     "entries": {"m5/armband": {"source": "<sha256>", "variants": 2,
                                "files": {"0": {"file": "armband_0.png",
                                                "size": [w, h],
                                                "pixels": "<sha256 of RGBA>"}}}}}

``source`` hashes the sprite module's source text, the source of every module
it imports (transitively) from inside its own art package plus any module it
names in ``BAKE_DEPS``, the pack palette file when declared, and
``TOOL_VERSION``. ``check()`` recomputes those hashes
(fast, no rendering) and additionally re-renders a deterministic 10 % sample
and byte-compares the RGBA pixels with the baked files.

Lint (``lint()``) is advisory - warnings are triaged into BUGS.md, never
auto-fixed: alpha fringe (dark semi-transparent halo next to opaque pixels;
tag ``shadow`` opts an asset with an intentional soft shadow out),
palette distance (assets tagged ``palette``, needs a pack palette), light
direction (assets tagged ``lit``: upper-left must read brighter than lower-
right, the ``_kit.bevel`` convention), text fit (modules declaring
``TEXT_BOXES``). Everything here is headless-safe (plain Surfaces, no display).
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .manifest import AssetDef, Manifest

__all__ = ["TOOL_VERSION", "BAKEINFO_SCHEMA", "BakeReport", "LintReport",
           "source_hash", "pixel_hash", "bake_pack", "check_pack", "lint_pack", "contact_sheet"]

TOOL_VERSION = "ae_bake/1"
BAKEINFO_SCHEMA = "ae.bakeinfo/1"
SAMPLE_EVERY = 10          # --check re-renders every 10th (id, variant) pair


# ---------------------------------------------------------------------------- hashing
def _module_source(modname: str) -> tuple[str, str] | None:
    spec = importlib.util.find_spec(modname)
    if spec is None or not spec.origin or not spec.origin.endswith(".py"):
        return None
    with open(spec.origin, "rb") as fh:
        return spec.origin, fh.read().decode("utf-8", "replace").replace("\r\n", "\n")


def _local_imports(src: str, modname: str, package_prefix: str) -> list[str]:
    """Names of modules imported by ``src`` that live under ``package_prefix``."""
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    pkg = modname.rsplit(".", 1)[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith(package_prefix):
                    out.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = pkg.split(".")
                base = ".".join(parts[: len(parts) - node.level + 1] + ([base] if base else []))
            if base.startswith(package_prefix):
                plain = False
                for a in node.names:
                    cand = base + "." + a.name
                    if _is_module(cand):
                        out.append(cand)
                    else:
                        plain = True          # a name defined in the module itself
                if plain or not node.names:
                    out.append(base)
    return out


def _declared_deps(src: str) -> list[str]:
    """``BAKE_DEPS = ("pkg.mod", ...)`` lets a sprite module name out-of-package painters it calls."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "BAKE_DEPS" for t in node.targets):
            try:
                val = ast.literal_eval(node.value)
            except ValueError:
                return []
            return [str(v) for v in val]
    return []


def _is_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def source_hash(a: AssetDef, root: str, palette: str | None = None) -> tuple[str, list[str]]:
    """sha256 over tool version + module source + transitive in-package imports + palette."""
    h = hashlib.sha256()
    h.update(TOOL_VERSION.encode())
    seen: list[str] = []
    if a.module:
        prefix = a.module.rsplit(".", 1)[0]
        todo = [a.module]
        while todo:
            m = todo.pop(0)
            if m in seen:
                continue
            got = _module_source(m)
            if got is None:
                continue
            seen.append(m)
            _, src = got
            h.update(m.encode())
            h.update(src.encode("utf-8"))
            for dep in _local_imports(src, m, prefix) + _declared_deps(src):
                if dep not in seen:
                    todo.append(dep)
    if palette:
        p = os.path.join(root, palette)
        if os.path.exists(p):
            with open(p, "rb") as fh:
                h.update(fh.read().replace(b"\r\n", b"\n"))
    return h.hexdigest(), seen


def pixel_hash(surf) -> str:
    import pygame
    return hashlib.sha256(pygame.image.tobytes(surf, "RGBA")).hexdigest()


def _bakeinfo_path(m: Manifest, root: str) -> Path:
    return Path(root) / (m.baked_dir or f"assets/baked/{m.pack}") / ".bakeinfo.json"


def read_bakeinfo(m: Manifest, root: str) -> dict:
    p = _bakeinfo_path(m, root)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {}


# ---------------------------------------------------------------------------- bake
@dataclass
class BakeReport:
    pack: str
    baked: int = 0
    checked: int = 0
    sampled: int = 0
    stale: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.stale or self.missing or self.mismatched or self.errors)

    def summary(self) -> str:
        return (f"pack {self.pack}: baked={self.baked} checked={self.checked} sampled={self.sampled} "
                f"stale={len(self.stale)} missing={len(self.missing)} mismatched={len(self.mismatched)} "
                f"errors={len(self.errors)} -> {'OK' if self.ok else 'FAIL'}")


def _render(a: AssetDef, variant: int):
    """Offline render: honours an optional ``bake_setup(variant)`` hook (tools only - the runtime
    registry never calls it) so world layers can put the game into the state a variant depicts."""
    mod = importlib.import_module(a.module)
    setup = getattr(mod, "bake_setup", None)
    if setup is not None:
        setup(variant)
    return mod.render(variant, 1)


def _variants(a: AssetDef) -> int:
    try:
        return int(getattr(importlib.import_module(a.module), "VARIANTS", a.variants))
    except Exception:
        return a.variants


def bake_pack(m: Manifest, root: str, *, only: set | None = None, verbose=print) -> BakeReport:
    """Render every variant of every rendered asset to its baked file; write .bakeinfo.json."""
    import pygame
    rep = BakeReport(m.pack)
    info = read_bakeinfo(m, root)
    entries = info.get("entries", {}) if info.get("schema") == BAKEINFO_SCHEMA else {}
    for a in sorted(m, key=lambda d: d.id):
        if not a.rendered or (only and a.id not in only):
            continue
        try:
            shash, _ = source_hash(a, root, m.palette)
            files = {}
            for v in range(_variants(a)):
                s = _render(a, v)
                out = Path(root) / a.baked_file(v)
                out.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(s, str(out))
                files[str(v)] = {"file": out.name, "size": list(s.get_size()), "pixels": pixel_hash(s)}
                rep.baked += 1
                if verbose:
                    verbose("baked %-28s v%-2d %dx%d" % (a.id, v, *s.get_size()))
            entries[a.id] = {"source": shash, "variants": len(files), "files": files}
        except Exception as e:   # noqa: BLE001
            rep.errors.append(f"{a.id}: {e!r}")
    doc = {"schema": BAKEINFO_SCHEMA, "pack": m.pack, "tool": TOOL_VERSION,
           "entries": {k: entries[k] for k in sorted(entries)}}
    p = _bakeinfo_path(m, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return rep


def check_pack(m: Manifest, root: str, *, sample_every: int = SAMPLE_EVERY, verbose=None) -> BakeReport:
    """Hash check (all rendered assets) + 10 % re-render sample. Never writes."""
    import pygame
    rep = BakeReport(m.pack)
    info = read_bakeinfo(m, root)
    entries = info.get("entries", {}) if info.get("schema") == BAKEINFO_SCHEMA else {}
    if info and info.get("tool") != TOOL_VERSION:
        rep.stale.append(f"{m.pack}: .bakeinfo tool {info.get('tool')!r} != {TOOL_VERSION!r}")
    pairs = []
    for a in sorted(m, key=lambda d: d.id):
        if not a.rendered:
            continue
        rep.checked += 1
        ent = entries.get(a.id)
        if ent is None:
            rep.missing.append(f"{a.id}: no .bakeinfo entry")
            continue
        shash, _ = source_hash(a, root, m.palette)
        if ent.get("source") != shash:
            rep.stale.append(f"{a.id}: source hash changed")
        nv = _variants(a)
        if ent.get("variants") != nv:
            rep.stale.append(f"{a.id}: variants {ent.get('variants')} != {nv}")
        for v in range(nv):
            f = Path(root) / a.baked_file(v)
            if not f.exists():
                rep.missing.append(f"{a.id} v{v}: {f} missing")
            else:
                pairs.append((a, v, f, ent.get("files", {}).get(str(v), {})))
    for i, (a, v, f, meta) in enumerate(pairs):
        if i % max(1, sample_every):
            continue
        rep.sampled += 1
        try:
            live = _render(a, v)
            baked = pygame.image.load(str(f))
            if baked.get_size() != live.get_size() or \
                    pygame.image.tobytes(baked, "RGBA") != pygame.image.tobytes(live, "RGBA"):
                rep.mismatched.append(f"{a.id} v{v}: baked pixels != live render")
            elif meta.get("pixels") and meta["pixels"] != pixel_hash(live):
                rep.mismatched.append(f"{a.id} v{v}: .bakeinfo pixel hash != live render")
        except Exception as e:   # noqa: BLE001
            rep.errors.append(f"{a.id} v{v}: {e!r}")
        if verbose:
            verbose("sampled %s v%d" % (a.id, v))
    return rep


# ---------------------------------------------------------------------------- lint
@dataclass
class LintReport:
    pack: str
    assets: int = 0
    warnings: list[str] = field(default_factory=list)
    checks: dict = field(default_factory=lambda: {"fringe": 0, "palette": 0, "lit": 0, "text": 0})

    def summary(self) -> str:
        c = self.checks
        return (f"lint {self.pack}: assets={self.assets} fringe={c['fringe']} palette={c['palette']} "
                f"lit={c['lit']} text={c['text']} warnings={len(self.warnings)}")


def _rgba_array(surf):
    import numpy as np
    import pygame
    w, h = surf.get_size()
    return np.frombuffer(pygame.image.tobytes(surf, "RGBA"), dtype=np.uint8).reshape(h, w, 4)


def lint_fringe(surf, *, dark: int = 48, limit: float = 0.02) -> tuple[int, int, float]:
    """(semi-transparent px, dark fringe px, ratio): fringe = alpha in 1..254, RGB all < dark,
    and 4-adjacent to an opaque pixel."""
    import numpy as np
    a = _rgba_array(surf)
    alpha = a[..., 3]
    semi = (alpha > 0) & (alpha < 255)
    n_semi = int(semi.sum())
    if n_semi == 0:
        return 0, 0, 0.0
    opaque = alpha == 255
    nb = np.zeros_like(opaque)
    nb[1:, :] |= opaque[:-1, :]
    nb[:-1, :] |= opaque[1:, :]
    nb[:, 1:] |= opaque[:, :-1]
    nb[:, :-1] |= opaque[:, 1:]
    darkpx = (a[..., 0] < dark) & (a[..., 1] < dark) & (a[..., 2] < dark)
    fr = int((semi & nb & darkpx).sum())
    return n_semi, fr, fr / n_semi


def lint_palette(surf, palette: list[tuple[int, int, int]], *, tol: int = 24) -> tuple[int, int, float]:
    """(opaque px, off-palette px, max distance): nearest-colour distance per opaque pixel."""
    import numpy as np
    a = _rgba_array(surf)
    op = a[..., 3] == 255
    px = a[op][:, :3].astype(np.int32)
    if len(px) == 0:
        return 0, 0, 0.0
    pal = np.array(palette, dtype=np.int32)
    d = np.sqrt(((px[:, None, :] - pal[None, :, :]) ** 2).sum(-1)).min(1)
    return int(len(px)), int((d > tol).sum()), float(d.max())


def lint_light(surf) -> tuple[float, float]:
    """(mean luma upper-left half, mean luma lower-right half) over opaque pixels."""
    import numpy as np
    a = _rgba_array(surf)
    h, w = a.shape[:2]
    op = a[..., 3] == 255
    luma = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    yy, xx = np.mgrid[0:h, 0:w]
    diag = (xx / max(1, w - 1) + yy / max(1, h - 1)) < 1.0
    ul = luma[op & diag]
    lr = luma[op & ~diag]
    return (float(ul.mean()) if len(ul) else 0.0, float(lr.mean()) if len(lr) else 0.0)


def lint_pack(m: Manifest, root: str, *, surfaces=None) -> LintReport:
    rep = LintReport(m.pack)
    palette = None
    if m.palette and os.path.exists(os.path.join(root, m.palette)):
        with open(os.path.join(root, m.palette), encoding="utf-8") as fh:
            palette = [tuple(c[:3]) for c in json.load(fh).get("colors", [])]
    for a in sorted(m, key=lambda d: d.id):
        if not a.rendered:
            continue
        rep.assets += 1
        mod = importlib.import_module(a.module)
        boxes = getattr(mod, "TEXT_BOXES", None)
        if boxes:
            rep.checks["text"] += 1
            tw = getattr(mod, "text_width", None)
            for (v, (bx, by, bw, bh), text) in boxes:
                width = tw(text) if tw else len(text) * 6 - 1
                if width > bw:
                    rep.warnings.append(f"text-fit {a.id} v{v}: {text!r} needs {width}px, box is {bw}px")
        for v in range(_variants(a)):
            s = (surfaces or {}).get((a.id, v)) or _render(a, v)
            n_semi, fr, ratio = lint_fringe(s)
            rep.checks["fringe"] += 1
            if "shadow" not in a.tags and n_semi >= 16 and ratio > 0.02 and fr >= 8:
                rep.warnings.append(f"alpha-fringe {a.id} v{v}: {fr}/{n_semi} dark semi-transparent edge px ({ratio:.1%})")
            if "palette" in a.tags and palette:
                rep.checks["palette"] += 1
                n_op, off, dmax = lint_palette(s, palette)
                if n_op and off / n_op > 0.05:
                    rep.warnings.append(f"palette {a.id} v{v}: {off}/{n_op} px > 24 from palette (max {dmax:.0f})")
            if "lit" in a.tags:
                rep.checks["lit"] += 1
                ul, lr = lint_light(s)
                if lr > ul * 1.05:
                    rep.warnings.append(f"light-dir {a.id} v{v}: lower-right brighter ({lr:.0f}) than upper-left ({ul:.0f})")
    return rep


# ---------------------------------------------------------------------------- sheet
def contact_sheet(m: Manifest, root: str, out_path: str, *, cols: int = 10, box: int = 288) -> int:
    """Grid of every variant (x1..x4 nearest, big layers shrunk), mid-grey background. Returns tile count."""
    import pygame
    tiles = []
    for a in sorted(m, key=lambda d: d.id):
        if not a.rendered:
            continue
        for v in range(_variants(a)):
            f = Path(root) / a.baked_file(v)
            s = pygame.image.load(str(f)) if f.exists() else _render(a, v)
            tiles.append(s)
    cw = ch = box + 12
    rows = max(1, (len(tiles) + cols - 1) // cols)
    sheet = pygame.Surface((cols * cw, rows * ch))
    sheet.fill((70, 66, 62))
    for i, s in enumerate(tiles):
        w, h = s.get_size()
        z = max(1, min(4, box // max(w, h)))
        if max(w, h) * z > box:
            k = box / max(w, h)
            big = pygame.transform.smoothscale(s, (max(1, int(w * k)), max(1, int(h * k))))
        else:
            big = pygame.transform.scale(s, (w * z, h * z))
        sheet.blit(big, ((i % cols) * cw + 6, (i // cols) * ch + 6))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(sheet, out_path)
    return len(tiles)
