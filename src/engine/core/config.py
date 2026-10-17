"""Layered settings: defaults < JSON file < environment < CLI overrides (§6.1)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

__all__ = ["Settings", "DEFAULTS", "ENV_MAP"]

DEFAULTS: dict[str, Any] = {
    "width": 1000, "height": 700, "tile_size": 64,
    "step_hz": 60, "max_steps": 5, "seed": 0,
    "video_driver": None,          # None = SDL default; "dummy" = headless
    "renderer3d": "gl",            # gl | software (legacy ACARISTAN_RENDERER)
    "cutscene3d": True,            # legacy ACARISTAN_CUTSCENE3D
    "window_title": "Call of Acaristan",
    "crash_dir": "crash_reports",
}
# environment variable -> (setting key, parser)
ENV_MAP = {
    "SDL_VIDEODRIVER": ("video_driver", str),
    "ACARISTAN_RENDERER": ("renderer3d", str),
    "ACARISTAN_CUTSCENE3D": ("cutscene3d", lambda v: v.strip() not in ("0", "false", "no", "")),
    "ACA_SEED": ("seed", int),
}


class Settings:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self._v = dict(DEFAULTS)
        self._src = {k: "default" for k in DEFAULTS}
        if values:
            self.update(values, "init")

    @classmethod
    def load(cls, path: str | os.PathLike | None = None, env: dict | None = None,
             overrides: dict[str, Any] | None = None) -> "Settings":
        s = cls()
        if path and Path(path).exists():
            s.update(json.loads(Path(path).read_text(encoding="utf-8")), f"file:{path}")
        env = os.environ if env is None else env
        for var, (key, parse) in ENV_MAP.items():
            if var in env:
                s.update({key: parse(env[var])}, f"env:{var}")
        if overrides:
            s.update(overrides, "cli")
        return s

    def update(self, values: dict[str, Any], source: str) -> None:
        for k, v in values.items():
            if k.startswith("_"):
                continue
            self._v[k] = v
            self._src[k] = source

    def get(self, key: str, default: Any = None) -> Any:
        return self._v.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._v[key]

    def source(self, key: str) -> str:
        return self._src.get(key, "unset")

    def as_dict(self) -> dict[str, Any]:
        return dict(self._v)
