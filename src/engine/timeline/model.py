"""timeline.model - the .timeline.json model and static validation (RPE6 §6.15).

A timeline is the sequencing layer of a cutscene: an ordered ``shots`` list
(each shot names a renderer *hook id* in ``scene`` plus its legacy payload -
``speaker``/``text``/``lighting``/flags) and/or keyframed ``tracks``
(``camera``/``light`` keys, ``fx``/``dialogue``/``caption``/``audio``/
``event`` clips) sampled deterministically by ``timeline.player``.

The legacy player advances shots on input, so shot durations are optional;
tracks are timed in the timeline's own unit (``duration_ms`` /
``metadata.time_unit`` - the M4 gameplay ladders run in frames).
``validate`` returns human-readable problems; loaders raise
:class:`TimelineError` on the first one.
"""
from __future__ import annotations

import json
from typing import Any

from .expr import check as _expr_check

__all__ = ["SCHEMA", "TimelineError", "Timeline", "validate", "from_dict", "loads_timeline", "load_timeline"]

SCHEMA = "ae.timeline/1"
_TOP = {"schema", "id", "duration_ms", "fps_hint", "letterbox", "ui_composite", "skippable",
        "set", "params", "shots", "tracks", "metadata"}
_TRACK_KINDS = {"camera", "light", "actor", "fx", "decal", "dialogue", "caption", "audio", "event", "shot"}
_KEY_TRACKS = {"camera", "light", "actor", "decal"}


class TimelineError(ValueError):
    """A timeline file is missing, malformed, or fails validation."""


class Timeline:
    __slots__ = ("id", "duration_ms", "shots", "tracks", "params", "set", "metadata", "source", "data")

    def __init__(self, data: dict, source: str = "") -> None:
        self.data = data
        self.id = data["id"]
        self.duration_ms = data.get("duration_ms")
        self.shots = data.get("shots", [])
        self.tracks = data.get("tracks", {})
        self.params = dict(data.get("params", {}))
        self.set = data.get("set")
        self.metadata = dict(data.get("metadata", {}))
        self.source = source

    def __len__(self) -> int:
        return len(self.shots)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate(data: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(data, dict):
        return ["timeline is not a JSON object"]
    for k in data:
        if k not in _TOP:
            out.append(f"unknown top-level key {k!r}")
    if data.get("schema") != SCHEMA:
        out.append(f"schema is {data.get('schema')!r}, expected {SCHEMA!r}")
    if not isinstance(data.get("id"), str) or not data["id"]:
        out.append("id missing")
    duration = data.get("duration_ms")
    if duration is not None and not (_is_num(duration) and duration >= 0):
        out.append("duration_ms must be a non-negative number")
    params = data.get("params", {})
    if not isinstance(params, dict):
        out.append("params is not an object")
        params = {}
    for name, v in params.items():
        if not _is_num(v):
            out.append(f"param {name!r} is not a number")
    shots = data.get("shots", [])
    if not isinstance(shots, list):
        out.append("shots is not a list")
        shots = []
    for i, shot in enumerate(shots):
        if not isinstance(shot, dict):
            out.append(f"shot {i}: not an object")
            continue
        if not isinstance(shot.get("scene"), str) or not shot["scene"]:
            out.append(f"shot {i}: scene (renderer hook id) missing")
        for key in ("speaker", "text"):
            if key in shot and shot[key] is not None and not isinstance(shot[key], str):
                out.append(f"shot {i}: {key} must be a string or null")
        if "duration_ms" in shot and not (_is_num(shot["duration_ms"]) and shot["duration_ms"] >= 0):
            out.append(f"shot {i}: duration_ms must be a non-negative number")
    tracks = data.get("tracks", {})
    if not isinstance(tracks, dict):
        out.append("tracks is not an object")
        tracks = {}
    env = {k: float(v) for k, v in params.items() if _is_num(v)}
    env.setdefault("k", 0.0)
    env.setdefault("t", 0.0)
    for name, track in tracks.items():
        kind = name.split(":")[0]
        if kind not in _TRACK_KINDS:
            out.append(f"track {name!r}: unknown track kind {kind!r}")
            continue
        if not isinstance(track, list):
            out.append(f"track {name!r}: not a list")
            continue
        prev_t = None
        for j, item in enumerate(track):
            if not isinstance(item, dict):
                out.append(f"track {name!r} item {j}: not an object")
                continue
            if kind in _KEY_TRACKS:
                t = item.get("t")
                if not _is_num(t):
                    out.append(f"track {name!r} key {j}: t must be a number")
                    continue
                if prev_t is not None and t < prev_t:
                    out.append(f"track {name!r}: keys out of order at key {j}")
                prev_t = t
                for field, v in item.items():
                    if isinstance(v, str) and field not in ("ease", "pose", "look_at", "cast", "outfit"):
                        problem = _expr_check(v, env)
                        if problem:
                            out.append(f"track {name!r} key {j} field {field!r}: {problem}")
            else:
                start = item.get("start", item.get("t"))
                end = item.get("end")
                if start is not None and not _is_num(start):
                    out.append(f"track {name!r} clip {j}: start must be a number")
                if end is not None and not _is_num(end):
                    out.append(f"track {name!r} clip {j}: end must be a number")
                if _is_num(start) and _is_num(end) and end < start:
                    out.append(f"track {name!r} clip {j}: end before start")
                if _is_num(duration) and _is_num(end) and end > duration:
                    out.append(f"track {name!r} clip {j}: end past duration_ms")
            if kind == "event" and not isinstance(item.get("name"), str):
                out.append(f"track {name!r} clip {j}: event clip needs a name")
    if not shots and not tracks:
        out.append("timeline has neither shots nor tracks")
    return out


def from_dict(data: dict, source: str = "") -> Timeline:
    problems = validate(data)
    if problems:
        raise TimelineError(f"{source or 'timeline'}: " + "; ".join(problems))
    return Timeline(data, source)


def loads_timeline(text: str, source: str = "<string>") -> Timeline:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise TimelineError(f"{source}: invalid JSON: {e}") from e
    return from_dict(data, source)


def load_timeline(path: str) -> Timeline:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        raise TimelineError(f"cannot read timeline {path}: {e}") from e
    return loads_timeline(text, path)
