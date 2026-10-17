"""render3d.presets - named 3D lighting moods (RPE6 §6.7 step 1, Phase 11).

A preset (``ae.lighting3d/1``) bundles the key light, fog and sky of a
scene so a set can switch mood with one word::

    "lighting": "night_interior"
    "lighting": {"preset": "office_day", "key": {"ambient": 0.5}}

A set's own ``light``/``fog`` blocks override single preset fields.
Preset files may be aliases (``{"alias": "exterior_night_rain"}``);
duplicate definitions are rejected by the library loader.  Two
presets blend with :func:`blend_presets` (timeline ``preset_blend``).
Pure data - no renderer imports.
"""
from __future__ import annotations

import json
import os

__all__ = ["PRESET_SCHEMA", "PresetError", "from_dict", "load_preset",
           "load_library", "resolve", "blend"]

PRESET_SCHEMA = "ae.lighting3d/1"
_KEY_FIELDS = ("direction", "ambient", "diffuse", "tint")
_FOG_FIELDS = ("color", "start", "end")


class PresetError(ValueError):
    """A lighting preset is missing, malformed, or unresolvable."""


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def from_dict(data: dict, source: str = "") -> dict:
    if not isinstance(data, dict):
        raise PresetError(f"{source or 'preset'}: not an object")
    if data.get("schema") != PRESET_SCHEMA:
        raise PresetError(f"{source or 'preset'}: schema is {data.get('schema')!r}")
    pid = data.get("id")
    if not isinstance(pid, str) or not pid:
        raise PresetError(f"{source or 'preset'}: id missing")
    if "alias" in data:
        if not isinstance(data["alias"], str) or not data["alias"]:
            raise PresetError(f"{source}: alias must be a preset id")
        return {"id": pid, "alias": data["alias"]}
    key = data.get("key") or {}
    fog = data.get("fog") or {}
    for name, fields in (("key", _KEY_FIELDS), ("fog", _FOG_FIELDS)):
        block = data.get(name)
        if block is not None:
            if not isinstance(block, dict):
                raise PresetError(f"{source}: {name} is not an object")
            for k in block:
                if k not in fields:
                    raise PresetError(f"{source}: unknown {name} field {k!r}")
    sky = data.get("sky")
    if sky is not None and not (isinstance(sky, list) and len(sky) == 2):
        raise PresetError(f"{source}: sky must be [top, bottom]")
    return {"id": pid, "key": dict(key), "fog": dict(fog), "sky": sky}


def load_preset(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as e:
        raise PresetError(f"cannot read preset {path}: {e}") from e
    except json.JSONDecodeError as e:
        raise PresetError(f"{path}: invalid JSON: {e}") from e
    return from_dict(data, path)


def load_library(dirpath: str) -> dict:
    """Load every ``*.preset.json`` in a directory into {id: preset}."""
    lib: dict = {}
    if not os.path.isdir(dirpath):
        return lib
    for name in sorted(os.listdir(dirpath)):
        if not name.endswith(".preset.json"):
            continue
        p = load_preset(os.path.join(dirpath, name))
        if p["id"] in lib:
            raise PresetError(f"duplicate lighting preset {p['id']!r}")
        lib[p["id"]] = p
    return lib


def _full(library: dict, pid: str, seen=()) -> dict:
    if pid in seen:
        raise PresetError(f"lighting preset alias cycle at {pid!r}")
    p = library.get(pid)
    if p is None:
        raise PresetError(f"unknown lighting preset {pid!r}")
    if "alias" in p:
        return _full(library, p["alias"], seen + (pid,))
    return p


def _lerp(a, b, k):
    if isinstance(a, list) and isinstance(b, list):
        return [_lerp(x, y, k) for x, y in zip(a, b)]
    if _is_num(a) and _is_num(b):
        return a + (b - a) * k
    return b if k >= 0.5 else a


def resolve(spec, library: dict) -> dict:
    """Resolve a lighting spec to {key, fog, sky} concrete values.

    ``spec`` is a preset id, ``{"preset": id, "key": {...},
    "fog": {...}}`` (partial overrides), or a literal
    ``{"key": ..., "fog": ...}`` block.  Returns fresh dicts.
    """
    if spec is None:
        return {"key": {}, "fog": {}, "sky": None}
    if isinstance(spec, str):
        base = _full(library, spec)
        return {"key": dict(base["key"]), "fog": dict(base["fog"]),
                "sky": base.get("sky")}
    if isinstance(spec, dict):
        out = {"key": {}, "fog": {}, "sky": None}
        if "preset" in spec:
            out = resolve(spec["preset"], library)
        for field in ("key", "fog"):
            for k, v in (spec.get(field) or {}).items():
                out[field][k] = list(v) if isinstance(v, list) else v
        if "sky" in spec:
            out["sky"] = spec["sky"]
        return out
    raise PresetError(f"lighting spec must be a preset id or object, got {spec!r}")


def blend(spec_a, spec_b, k: float, library: dict) -> dict:
    """Cross-fade two lighting specs (``k`` 0..1) - timeline blends."""
    a, b = resolve(spec_a, library), resolve(spec_b, library)
    k = max(0.0, min(1.0, float(k)))
    out = {"key": {}, "fog": {}, "sky": None}
    for field in ("key", "fog"):
        for name in set(a[field]) | set(b[field]):
            if name in a[field] and name in b[field]:
                out[field][name] = _lerp(a[field][name], b[field][name], k)
            elif name in b[field]:
                out[field][name] = b[field][name]
            else:
                out[field][name] = a[field][name]
    if a["sky"] and b["sky"]:
        out["sky"] = [_lerp(a["sky"][0], b["sky"][0], k),
                      _lerp(a["sky"][1], b["sky"][1], k)]
    else:
        out["sky"] = b["sky"] or a["sky"]
    return out
