"""level.model - the .level.json model, validation and (de)serialisation (RPE6 §6.16).

Fields (schema ``ae.level/1``)::

    id            str                       e.g. "m5.quarter"
    name          str                       human title
    tile_size     int                       px per tile (the game's TILE_SIZE)
    layers        {name: [str, ...]}        tile grids; all rows of a layer equal length
    objects       [{id?, kind, tile:[c,r] | pos:[x,y], props:{...}}]
    triggers      [{id, kind, tile/rect, props}]   stage transitions, dialogue starts, ...
    paths         [{id, points:[[c,r], ...], props}] patrols, convoy routes
    lights        [{id, tile/pos, radius, color, kind}]
    decor         [{asset, variant, layer, tile/pos, props}]   baked decor placements
    procedural_decor [{id, seed, params}]   seeded painters, run at bake time (R2 rng rule)
    metadata      {objective_key, music, ambient, weather:{rain, density}, ...}

Unknown top-level keys are rejected (a typo in data must fail loudly, R1); unknown
keys *inside* an entry's ``props`` are the mission's business and pass through.
"""
from __future__ import annotations

import json
from typing import Any

__all__ = ["SCHEMA", "LevelError", "Level", "validate", "from_dict", "to_dict", "loads_level", "load_level"]

SCHEMA = "ae.level/1"
_TOP = {"schema", "id", "name", "tile_size", "layers", "objects", "triggers", "paths", "lights", "decor",
        "procedural_decor", "metadata"}
_LISTS = ("objects", "triggers", "paths", "lights", "decor", "procedural_decor")


class LevelError(ValueError):
    """A level file is missing, malformed, or fails validation."""


class Level:
    __slots__ = ("id", "name", "tile_size", "layers", "objects", "triggers", "paths", "lights", "decor",
                 "procedural_decor", "metadata", "source")

    def __init__(self, data: dict, source: str = "") -> None:
        self.id = data["id"]
        self.name = data.get("name", self.id)
        self.tile_size = int(data.get("tile_size", 64))
        self.layers = {k: [str(r) for r in v] for k, v in data.get("layers", {}).items()}
        for k in _LISTS:
            setattr(self, k, list(data.get(k, [])))
        self.metadata = dict(data.get("metadata", {}))
        self.source = source

    def grid(self, layer: str = "floor") -> list[str]:
        """A *copy* of the tile layer as list[str] (callers may rebind markers, never mutate the level)."""
        return list(self.layers[layer])

    def size(self, layer: str = "floor") -> tuple[int, int]:
        g = self.layers[layer]
        return (len(g[0]) if g else 0, len(g))

    def objects_of(self, kind: str) -> list[dict]:
        return [o for o in self.objects if o.get("kind") == kind]

    def path(self, path_id: str) -> list[tuple[int, int]] | None:
        for p in self.paths:
            if p.get("id") == path_id:
                return [tuple(pt) for pt in p["points"]]
        return None

    def to_dict(self) -> dict:
        return to_dict(self)


def validate(data: Any) -> list[str]:
    """Human-readable problems with ``data`` (empty list = clean). Never raises."""
    out: list[str] = []
    if not isinstance(data, dict):
        return ["level is not a JSON object"]
    for k in data:
        if k not in _TOP:
            out.append(f"unknown top-level key {k!r}")
    if data.get("schema") != SCHEMA:
        out.append(f"schema is {data.get('schema')!r}, expected {SCHEMA!r}")
    if not isinstance(data.get("id"), str) or not data["id"]:
        out.append("id missing")
    ts = data.get("tile_size", 64)
    if not isinstance(ts, int) or ts <= 0:
        out.append(f"tile_size {ts!r} is not a positive int")
    layers = data.get("layers")
    if not isinstance(layers, dict) or not layers:
        out.append("layers missing (need at least the floor layer)")
        layers = {}
    for name, g in layers.items():
        if not isinstance(g, list) or not g or not all(isinstance(r, str) for r in g):
            out.append(f"layer {name!r}: not a non-empty list of strings")
            continue
        w = len(g[0])
        if w == 0 or any(len(r) != w for r in g):
            out.append(f"layer {name!r}: ragged rows (widths {[len(r) for r in g][:6]}...)")
    sizes = {n: (len(g[0]), len(g)) for n, g in layers.items() if g and all(isinstance(r, str) for r in g)}
    if len(set(sizes.values())) > 1:
        out.append(f"layers disagree on size: {sizes}")
    for k in _LISTS:
        v = data.get(k, [])
        if not isinstance(v, list) or not all(isinstance(e, dict) for e in v):
            out.append(f"{k}: not a list of objects")
    for o in data.get("objects", []) if isinstance(data.get("objects"), list) else []:
        if isinstance(o, dict) and "kind" not in o:
            out.append(f"object without kind: {str(o)[:60]}")
    for p in data.get("paths", []) if isinstance(data.get("paths"), list) else []:
        if isinstance(p, dict):
            pts = p.get("points")
            if not isinstance(pts, list) or len(pts) < 2:
                out.append(f"path {p.get('id')!r}: needs >= 2 points")
    if not isinstance(data.get("metadata", {}), dict):
        out.append("metadata is not an object")
    return out


def from_dict(data: dict, source: str = "") -> Level:
    problems = validate(data)
    if problems:
        raise LevelError(f"{source or 'level'}: " + "; ".join(problems))
    return Level(data, source)


def to_dict(level: Level) -> dict:
    return {"schema": SCHEMA, "id": level.id, "name": level.name, "tile_size": level.tile_size,
            "layers": {k: list(v) for k, v in level.layers.items()},
            "objects": level.objects, "triggers": level.triggers, "paths": level.paths, "lights": level.lights,
            "decor": level.decor, "procedural_decor": level.procedural_decor, "metadata": level.metadata}


def loads_level(text: str, source: str = "<string>") -> Level:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise LevelError(f"{source}: invalid JSON: {e}") from e
    return from_dict(data, source)


def load_level(path: str) -> Level:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        raise LevelError(f"cannot read level {path}: {e}") from e
    return loads_level(text, path)
