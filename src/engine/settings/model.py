"""settings.model - typed, layered settings (RPE6 §6.18, Phase 9).

A *schema* is a list of :class:`Field` records owned by the game (the
kernel is game-agnostic).  Values resolve through layers, lowest first:
schema defaults < persisted file dict < environment dict < explicit
overrides.  Every value is coerced and range/enum-checked; unknown keys
are preserved verbatim (forward compatibility with newer settings
files) but reported.  :class:`Settings` adds change notification - the
``SettingsChanged`` hook systems subscribe to so settings apply live.

Environment keys are ``<PREFIX><FIELD_NAME_UPPER>`` (e.g.
``ACARISTAN_SHAKE_SCALE=50``); unparsable env values are ignored with a
problem note, never fatal.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

__all__ = ["Field", "Settings", "coerce", "resolve", "env_layer", "BOOL", "INT", "FLOAT", "STR", "ENUM"]

BOOL, INT, FLOAT, STR, ENUM = "bool", "int", "float", "str", "enum"


class Field:
    __slots__ = ("name", "kind", "default", "section", "minimum", "maximum", "values")

    def __init__(self, name: str, kind: str, default, section: str = "general",
                 minimum=None, maximum=None, values=None):
        self.name = name
        self.kind = kind
        self.default = default
        self.section = section
        self.minimum = minimum
        self.maximum = maximum
        self.values = tuple(values) if values is not None else None

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"Field({self.name!r}, {self.kind!r}, {self.default!r})"


def coerce(field: Field, value):
    """(ok, coerced) - strict about types the way the legacy store was:
    a wrong-typed value falls back to the default rather than guessing."""
    kind = field.kind
    if kind == BOOL:
        if type(value) is not bool:
            return False, field.default
        return True, value
    if kind == INT:
        if type(value) is not int:  # bool is an int subclass: excluded on purpose
            return False, field.default
        v = value
    elif kind == FLOAT:
        if type(value) not in (int, float) or type(value) is bool:
            return False, field.default
        v = float(value)
    elif kind == STR:
        if not isinstance(value, str):
            return False, field.default
        return True, value
    elif kind == ENUM:
        if value not in (field.values or ()):
            return False, field.default
        return True, value
    else:  # pragma: no cover - schema author error
        raise ValueError(f"unknown field kind {kind!r}")
    if field.minimum is not None:
        v = max(field.minimum, v)
    if field.maximum is not None:
        v = min(field.maximum, v)
    return True, v


def resolve(schema, *layers, keep_unknown: bool = True):
    """(values, problems) after applying dict layers in order."""
    values: dict[str, Any] = {}
    problems: list[str] = []
    fields = {f.name: f for f in schema}
    for f in schema:
        values[f.name] = f.default
    for layer in layers:
        if not layer:
            continue
        for key, raw in layer.items():
            field = fields.get(key)
            if field is None:
                if keep_unknown:
                    values[key] = raw
                else:
                    problems.append(f"unknown setting {key!r} dropped")
                continue
            ok, v = coerce(field, raw)
            if not ok:
                problems.append(f"setting {key!r}: {raw!r} invalid for {field.kind}, using {v!r}")
            values[key] = v
    return values, problems


def env_layer(schema, environ: Mapping, prefix: str = "ACARISTAN_") -> dict:
    """Parse ``<prefix><NAME>`` env entries for schema fields into a layer."""
    out: dict[str, Any] = {}
    for f in schema:
        raw = environ.get(prefix + f.name.upper())
        if raw is None:
            continue
        if f.kind == BOOL:
            out[f.name] = raw.strip().lower() in ("1", "true", "yes", "on")
        elif f.kind == INT:
            try:
                out[f.name] = int(raw)
            except ValueError:
                continue
        elif f.kind == FLOAT:
            try:
                out[f.name] = float(raw)
            except ValueError:
                continue
        elif f.kind == ENUM:
            out[f.name] = int(raw) if raw.lstrip("-").isdigit() else raw
        else:
            out[f.name] = raw
    return out


class Settings:
    """Live settings over a schema: layered load, validated set, listeners."""

    def __init__(self, schema, *layers):
        self.schema = list(schema)
        self._fields = {f.name: f for f in self.schema}
        self.values, self.problems = resolve(self.schema, *layers)
        self._listeners: list[Callable] = []

    def get(self, name, default=None):
        return self.values.get(name, default)

    def __getitem__(self, name):
        return self.values[name]

    def __contains__(self, name):
        return name in self.values

    def subscribe(self, fn: Callable) -> Callable:
        """fn(name, old, new) on every effective change. Returns fn."""
        self._listeners.append(fn)
        return fn

    def set(self, name, value) -> bool:
        """Validate + store; fires listeners only on an effective change."""
        field = self._fields.get(name)
        if field is not None:
            ok, value = coerce(field, value)
            if not ok:
                return False
        old = self.values.get(name)
        if old == value and name in self.values:
            return True
        self.values[name] = value
        for fn in list(self._listeners):
            fn(name, old, value)
        return True

    def update(self, layer: Mapping) -> list[str]:
        """Apply a layer; returns problem notes; fires per changed key."""
        values, problems = resolve(self.schema, self.values, dict(layer))
        for name, v in values.items():
            if self.values.get(name) != v:
                old = self.values.get(name)
                self.values[name] = v
                for fn in list(self._listeners):
                    fn(name, old, v)
        return problems

    def to_dict(self) -> dict:
        return dict(self.values)
