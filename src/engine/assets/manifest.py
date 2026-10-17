"""Content-pack manifests (§6.5): ``ae.manifest/1``.

A manifest lists the assets of one pack with stable ids ``<pack>/<name>``.
Kinds: ``image`` (PNG on disk), ``sprite_def`` (Python module with
``render(variant, scale) -> Surface`` and ``VARIANTS``), ``layer`` (a large
baked sprite_def, one variant per key), ``sheet``, ``font``, ``sound``,
``music``, ``data``. Phase 3 bakes/validates ``sprite_def`` and ``layer`` and
resolves ``image``; the other kinds are declared and validated only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.core import SchemaError

__all__ = ["SCHEMA", "KINDS", "AssetDef", "Manifest", "load_manifest"]

SCHEMA = "ae.manifest/1"
KINDS = ("image", "sprite_def", "sheet", "font", "sound", "music", "data", "layer")
_RENDERED = ("sprite_def", "layer")


@dataclass(frozen=True)
class AssetDef:
    id: str
    kind: str
    pack: str
    module: str | None = None          # sprite_def / layer: importable module name
    path: str | None = None            # image / sound / music / font / data: file, repo-relative
    variants: int = 1
    baked: str | None = None           # sprite_def / layer: baked file pattern with {variant}
    pivot: tuple[int, int] | None = None
    size: tuple[int, int] | None = None
    tags: tuple[str, ...] = ()
    strings: tuple[str, ...] = ()
    fallback: str | None = None        # id of another asset used when this one cannot resolve
    extra: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.id.split("/", 1)[1] if "/" in self.id else self.id

    @property
    def rendered(self) -> bool:
        return self.kind in _RENDERED

    def baked_file(self, variant: int = 0) -> str | None:
        return self.baked.format(variant=variant, name=self.name) if self.baked else None


@dataclass
class Manifest:
    pack: str
    path: Path
    assets: dict[str, AssetDef]
    baked_dir: str | None = None
    palette: str | None = None

    def __iter__(self):
        return iter(self.assets.values())

    def __len__(self) -> int:
        return len(self.assets)


def _pair(v: Any, what: str) -> tuple[int, int] | None:
    if v is None:
        return None
    if not (isinstance(v, (list, tuple)) and len(v) == 2):
        raise SchemaError(f"{what}: expected [w, h], got {v!r}")
    return (int(v[0]), int(v[1]))


def parse_manifest(doc: dict, path: Path | str = "<memory>") -> Manifest:
    """Validate a manifest document and build the asset table (raises SchemaError)."""
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise SchemaError(f"{path}: schema must be {SCHEMA!r}, got {doc.get('schema') if isinstance(doc, dict) else doc!r}")
    pack = doc.get("pack")
    if not pack or not isinstance(pack, str):
        raise SchemaError(f"{path}: 'pack' must be a non-empty string")
    baked_dir = doc.get("baked_dir")
    assets: dict[str, AssetDef] = {}
    for i, a in enumerate(doc.get("assets", ())):
        where = f"{path}: assets[{i}]"
        if not isinstance(a, dict):
            raise SchemaError(f"{where}: expected an object")
        aid, kind = a.get("id"), a.get("kind")
        if not aid or not isinstance(aid, str) or not aid.startswith(pack + "/"):
            raise SchemaError(f"{where}: id must be '{pack}/<name>', got {aid!r}")
        if kind not in KINDS:
            raise SchemaError(f"{where}: kind {kind!r} not in {KINDS}")
        if aid in assets:
            raise SchemaError(f"{where}: duplicate id {aid!r}")
        if kind in _RENDERED and not a.get("module"):
            raise SchemaError(f"{where}: {kind} needs 'module'")
        if kind not in _RENDERED and not a.get("path"):
            raise SchemaError(f"{where}: {kind} needs 'path'")
        variants = int(a.get("variants", 1))
        if variants < 1:
            raise SchemaError(f"{where}: variants must be >= 1")
        baked = a.get("baked")
        if baked is None and kind in _RENDERED and baked_dir:
            baked = f"{baked_dir}/{aid.split('/', 1)[1]}_{{variant}}.png"
        known = {"id", "kind", "module", "path", "variants", "baked", "pivot", "size", "tags", "strings", "fallback"}
        assets[aid] = AssetDef(
            id=aid, kind=kind, pack=pack, module=a.get("module"), path=a.get("path"), variants=variants,
            baked=baked, pivot=_pair(a.get("pivot"), where + ".pivot"), size=_pair(a.get("size"), where + ".size"),
            tags=tuple(a.get("tags", ())), strings=tuple(a.get("strings", ())), fallback=a.get("fallback"),
            extra={k: v for k, v in a.items() if k not in known})
    for a in assets.values():
        if a.fallback and a.fallback not in assets:
            raise SchemaError(f"{path}: {a.id}: fallback {a.fallback!r} is not in the pack")
    return Manifest(pack=pack, path=Path(path), assets=assets, baked_dir=baked_dir, palette=doc.get("palette"))


def load_manifest(path: str | Path) -> Manifest:
    p = Path(path)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SchemaError(f"{p}: cannot read manifest: {e}") from e
    return parse_manifest(doc, p)
