"""engine.world._component - ``@component`` dataclasses and the schema registry (RPE6 §6.4, A.1).

A component is a plain dataclass registered by class name. The registry is what the
inspector, the prefab loader and ``tools/ae_dump_components.py`` read; nothing here
touches pygame or game code.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Iterator

from engine.core import SchemaError

__all__ = [
    "component",
    "component_type",
    "component_types",
    "fields_of",
    "is_component",
    "schema",
    "to_dict",
    "from_dict",
]

_REGISTRY: dict[str, type] = {}


def component(cls=None, *, version: int = 1):
    """Register a dataclass as a component type (name = class name, versioned).

    Works bare (``@component``) or with arguments (``@component(version=2)``). The
    class must already be a dataclass; registering two different classes under one
    name is an error (components are looked up by name in prefabs and dumps).
    """

    def _register(c):
        if not dataclasses.is_dataclass(c):
            raise SchemaError(f"component {c.__name__!r} must be a dataclass")
        prev = _REGISTRY.get(c.__name__)
        if prev is not None and prev is not c:
            # Module reloads re-register the same source; a *different* class is a clash.
            if getattr(prev, "__module__", None) != getattr(c, "__module__", None):
                raise SchemaError(f"component name {c.__name__!r} already registered by {prev.__module__}")
        c.__ae_component__ = True
        c.__ae_version__ = int(getattr(c, "__ae_version__", version))
        _REGISTRY[c.__name__] = c
        return c

    return _register if cls is None else _register(cls)


def is_component(kind: Any) -> bool:
    """True for registered component classes (not instances)."""
    return isinstance(kind, type) and _REGISTRY.get(kind.__name__) is kind


def component_type(name: str) -> type:
    """Registered class for ``name``; ``SchemaError`` when unknown."""
    try:
        return _REGISTRY[name]
    except KeyError:
        raise SchemaError(f"unknown component {name!r}") from None


def component_types() -> Iterator[type]:
    """Registered component classes in registration order."""
    return iter(list(_REGISTRY.values()))


def fields_of(kind: type) -> tuple[dataclasses.Field, ...]:
    return dataclasses.fields(kind)


def schema() -> dict[str, list[tuple[str, str]]]:
    """``{name: [(field, type_repr), ...]}`` for every registered component."""
    out: dict[str, list[tuple[str, str]]] = {}
    for name, c in _REGISTRY.items():
        out[name] = [(f.name, _type_repr(f.type)) for f in dataclasses.fields(c)]
    return out


def to_dict(comp: Any) -> dict[str, Any]:
    """Field dict of a component instance (views included: reads each declared field)."""
    kind = _kind_of(comp)
    return {f.name: _plain(getattr(comp, f.name)) for f in dataclasses.fields(kind)}


def from_dict(kind: type, data: dict[str, Any]):
    """Instantiate ``kind`` from a field dict; unknown keys are a ``SchemaError``."""
    names = {f.name for f in dataclasses.fields(kind)}
    bad = sorted(set(data) - names)
    if bad:
        raise SchemaError(f"{kind.__name__}: unknown field(s) {bad}")
    kw = {}
    for f in dataclasses.fields(kind):
        if f.name in data:
            v = data[f.name]
            kw[f.name] = set(v) if _is_set_field(f) and isinstance(v, (list, tuple)) else v
    return kind(**kw)


def _kind_of(comp: Any) -> type:
    kind = getattr(comp, "__ae_view_of__", None) or type(comp)
    if not is_component(kind):
        raise SchemaError(f"{type(comp).__name__} is not a component instance")
    return kind


def _is_set_field(f: dataclasses.Field) -> bool:
    t = f.type
    return t is set or (isinstance(t, str) and t.startswith("set"))


def _type_repr(t: Any) -> str:
    if isinstance(t, str):
        return t
    return getattr(t, "__name__", None) or str(t)


def _plain(v: Any) -> Any:
    if isinstance(v, (set, frozenset)):
        return sorted(v, key=repr)
    if isinstance(v, tuple):
        return list(v)
    return v
