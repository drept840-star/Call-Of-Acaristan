"""engine.level - data-driven levels (RPE6 §6.16, Phase 7).

A ``.level.json`` file is the native level format; a Tiled ``.tmj`` importer covers
editor-authored maps. The runtime tile contract is unchanged from the legacy game:
tile layers are ``list[str]`` grids, one character per tile, markers riding inside
the strings. This package only *loads and validates* data - it never imports game
code, and loading performs no I/O beyond the file given.

    from engine.level import load_level
    lvl = load_level("src/game/content/levels/m5_quarter.level.json")
    grid = lvl.grid("floor")           # list[str]
    spawns = lvl.objects(kind="spawn")

Schema ``ae.level/1`` (see ``model.Level`` for the fields); ``validate`` returns a
list of human-readable problems (empty = clean), ``load_level`` raises
``LevelError`` on the first one.
"""
from __future__ import annotations

from .model import SCHEMA, Level, LevelError, from_dict, load_level, loads_level, to_dict, validate
from .tiled import TiledError, from_tiled

__all__ = ["SCHEMA", "Level", "LevelError", "TiledError", "from_dict", "from_tiled", "load_level", "loads_level",
           "to_dict", "validate"]
