"""engine.world.prefab - data-defined entity templates with inheritance (RPE6 §6.4, B.4).

File format (``*.prefab.json``, one prefab per file or a list under ``"prefabs"``)::

    {"schema": "ae.prefab/1", "id": "m5/guard_raider", "extends": "m5/guard_base",
     "components": {"Health": {"max": 70}, "Tags": {"set": ["guard", "raider"]}}}

Resolution merges the ``extends`` chain field by field (child wins); ``overrides``
at instantiation time are a third layer. ``diff()`` reports what a prefab changes
relative to its parent - that is what the inspector shows.
"""
from __future__ import annotations

import json
import os
from typing import Any, Iterable

from engine.core import SchemaError

from ._component import component_type, from_dict
from .entity import EntityId, World

__all__ = ["PREFAB_SCHEMA", "PrefabLibrary", "load_prefabs"]

PREFAB_SCHEMA = "ae.prefab/1"


class PrefabLibrary:
    def __init__(self, prefabs: Iterable[dict[str, Any]] = ()) -> None:
        self._raw: dict[str, dict[str, Any]] = {}
        for p in prefabs:
            self.add(p)

    # ── authoring ──────────────────────────────────────────────────────────
    def add(self, prefab: dict[str, Any]) -> None:
        if prefab.get("schema", PREFAB_SCHEMA) != PREFAB_SCHEMA:
            raise SchemaError(f"prefab schema {prefab.get('schema')!r} != {PREFAB_SCHEMA!r}")
        pid = prefab.get("id")
        if not isinstance(pid, str) or not pid:
            raise SchemaError("prefab needs a non-empty string 'id'")
        comps = prefab.get("components", {})
        if not isinstance(comps, dict) or any(not isinstance(v, dict) for v in comps.values()):
            raise SchemaError(f"prefab {pid!r}: 'components' must map names to field dicts")
        self._raw[pid] = {"id": pid, "extends": prefab.get("extends"), "components": comps}

    def ids(self) -> list[str]:
        return sorted(self._raw)

    def __contains__(self, pid: object) -> bool:
        return pid in self._raw

    def raw(self, pid: str) -> dict[str, Any]:
        try:
            return self._raw[pid]
        except KeyError:
            raise SchemaError(f"unknown prefab {pid!r}") from None

    # ── resolution ─────────────────────────────────────────────────────────
    def chain(self, pid: str) -> list[str]:
        """``[root, ..., pid]`` following ``extends``; cycles and dangling parents are errors."""
        out: list[str] = []
        seen: set[str] = set()
        cur: str | None = pid
        while cur is not None:
            if cur in seen:
                raise SchemaError(f"prefab {pid!r}: 'extends' cycle at {cur!r}")
            seen.add(cur)
            out.append(cur)
            cur = self.raw(cur).get("extends")
        out.reverse()
        return out

    def resolve(self, pid: str, overrides: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
        """Merged ``{component_name: {field: value}}`` for ``pid`` (+ optional overrides)."""
        merged: dict[str, dict[str, Any]] = {}
        for anc in self.chain(pid):
            for cname, fields in self.raw(anc)["components"].items():
                merged.setdefault(cname, {}).update(fields)
        for cname, fields in (overrides or {}).items():
            if not isinstance(fields, dict):
                raise SchemaError(f"override for {cname!r} must be a field dict")
            merged.setdefault(cname, {}).update(fields)
        return merged

    def diff(self, pid: str) -> dict[str, dict[str, Any]]:
        """Fields ``pid`` sets that differ from (or add to) its resolved parent."""
        raw = self.raw(pid)
        parent = raw.get("extends")
        base = self.resolve(parent) if parent else {}
        out: dict[str, dict[str, Any]] = {}
        for cname, fields in raw["components"].items():
            for k, v in fields.items():
                if base.get(cname, {}).get(k, _MISSING) != v:
                    out.setdefault(cname, {})[k] = v
        return out

    # ── instantiation ──────────────────────────────────────────────────────
    def build(self, pid: str, overrides: dict[str, dict[str, Any]] | None = None) -> list[Any]:
        """Component instances for ``pid`` (unknown component names / fields raise ``SchemaError``)."""
        comps = []
        for cname, fields in self.resolve(pid, overrides).items():
            comps.append(from_dict(component_type(cname), fields))
        return comps

    def instantiate(self, world: World, pid: str, overrides: dict[str, dict[str, Any]] | None = None,
                    *extra: Any) -> EntityId:
        return world.spawn(*self.build(pid, overrides), *extra)


_MISSING = object()


def load_prefabs(path: str, library: PrefabLibrary | None = None) -> PrefabLibrary:
    """Load every ``*.prefab.json`` under ``path`` (a directory) or the single file ``path``."""
    lib = library or PrefabLibrary()
    files: list[str] = []
    if os.path.isdir(path):
        for dp, _dn, fn in os.walk(path):
            files.extend(os.path.join(dp, f) for f in fn if f.endswith(".prefab.json"))
        files.sort()
    elif os.path.isfile(path):
        files = [path]
    else:
        raise SchemaError(f"prefab path not found: {path}")
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        items = data["prefabs"] if isinstance(data, dict) and "prefabs" in data else [data]
        for item in items:
            try:
                lib.add(item)
            except SchemaError as e:
                raise SchemaError(f"{f}: {e}") from None
    return lib
