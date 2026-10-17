"""level.tiled - Tiled JSON (.tmj) importer (RPE6 §6.16).

Converts the subset of Tiled's format the game can consume into an ``ae.level/1``
dict: tile layers encoded as CSV or row strings become character grids through a
caller-supplied ``gid -> char`` map (Tiled speaks gids; our levels speak the
legacy one-char tile grammar), object layers become objects/triggers/paths
(rect → trigger, polyline → path, point → object), and map properties land in
``metadata``. The importer is pure - no I/O, no pygame.
"""
from __future__ import annotations

import json
from typing import Any

from .model import SCHEMA, Level, LevelError, from_dict

__all__ = ["TiledError", "from_tiled"]


class TiledError(LevelError):
    """The .tmj input is outside the supported subset."""


def _props(obj: dict) -> dict:
    out = {}
    for p in obj.get("properties", []) or []:
        out[p.get("name")] = p.get("value")
    return out


def _tile_rows(layer: dict, gid_char: dict[int, str]) -> list[str]:
    data = layer.get("data")
    w, h = int(layer["width"]), int(layer["height"])
    if isinstance(data, str):                      # already character rows, one per line
        rows = data.splitlines()
        if len(rows) != h or any(len(r) != w for r in rows):
            raise TiledError(f"layer {layer.get('name')!r}: string data is not {w}x{h}")
        return rows
    if not isinstance(data, list) or len(data) != w * h:
        raise TiledError(f"layer {layer.get('name')!r}: data is not a {w}x{h} gid array")
    rows = []
    for r in range(h):
        chars = []
        for gid in data[r * w:(r + 1) * w]:
            ch = gid_char.get(int(gid))
            if ch is None:
                raise TiledError(f"layer {layer.get('name')!r}: no char mapped for gid {gid}")
            chars.append(ch)
        rows.append("".join(chars))
    return rows


def from_tiled(data: dict | str, gid_char: dict[int, str], *, level_id: str = "", tile_size: int | None = None) -> Level:
    """Build a ``Level`` from parsed .tmj ``data`` (or its JSON text)."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise TiledError(f"invalid .tmj JSON: {e}") from e
    if not isinstance(data, dict) or data.get("type") != "map":
        raise TiledError("not a Tiled map (type != 'map')")
    ts = tile_size if tile_size is not None else int(data.get("tilewidth", 64))
    layers: dict[str, list[str]] = {}
    objects, triggers, paths = [], [], []
    for layer in data.get("layers", []):
        ltype = layer.get("type")
        if ltype == "tilelayer":
            layers[str(layer.get("name", "floor"))] = _tile_rows(layer, gid_char)
        elif ltype == "objectgroup":
            for o in layer.get("objects", []):
                props = _props(o)
                kind = o.get("type") or props.pop("kind", "prop")
                tile = [int(o.get("x", 0)) // ts, int(o.get("y", 0)) // ts]
                entry = {"id": o.get("name") or f"{kind}@{tile[0]},{tile[1]}", "kind": kind, "tile": tile,
                         "props": props}
                if o.get("polyline"):
                    pts = [[tile[0] + int(p["x"]) // ts, tile[1] + int(p["y"]) // ts] for p in o["polyline"]]
                    paths.append({"id": entry["id"], "points": pts, "props": props})
                elif float(o.get("width", 0)) > 0 or float(o.get("height", 0)) > 0:
                    entry["rect"] = [tile[0], tile[1], max(1, int(o.get("width", 0)) // ts),
                                     max(1, int(o.get("height", 0)) // ts)]
                    triggers.append(entry)
                else:
                    objects.append(entry)
    out: dict[str, Any] = {"schema": SCHEMA, "id": level_id or str(data.get("name") or "tiled.level"),
                           "name": str(data.get("name") or level_id or "tiled level"), "tile_size": ts,
                           "layers": layers, "objects": objects, "triggers": triggers, "paths": paths,
                           "metadata": _props(data)}
    return from_dict(out, source="tiled")
