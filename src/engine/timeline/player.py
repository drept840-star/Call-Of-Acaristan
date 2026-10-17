"""timeline.player - deterministic sampling of a Timeline at any t (RPE6 §6.15).

The player is pure: ``sample(t)`` returns the keyframed track values
(linear or eased interpolation between keys, expressions evaluated against
the timeline params with ``k`` = normalised progress and ``t`` bound), the
clips active at ``t`` per clip track, and - at the ``t`` where a clip
starts - the events due.  No state leaks between samples except the
explicit event cursor used by ``events_between``; seeking is exact, so
editor scrubbing and gauntlet frames at a fixed ``t`` are reproducible.
"""
from __future__ import annotations

from typing import Any

from .expr import evaluate
from .model import Timeline

__all__ = ["TimelinePlayer", "Sample"]

_EASE = {
    "linear": lambda u: u,
    "ease_in": lambda u: u * u,
    "ease_out": lambda u: 1.0 - (1.0 - u) ** 2,
    "ease_in_out": lambda u: u * u * (3.0 - 2.0 * u),
    "smoothstep": lambda u: u * u * (3.0 - 2.0 * u),
}

_SKIP_FIELDS = {"t", "ease"}


class Sample:
    """One sampled instant: ``values[track]`` dicts + ``active[track]`` clips."""

    __slots__ = ("t", "values", "active", "shot", "shot_index")

    def __init__(self, t, values, active, shot, shot_index):
        self.t = t
        self.values = values
        self.active = active
        self.shot = shot
        self.shot_index = shot_index

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"Sample(t={self.t!r}, shot={self.shot_index!r}, tracks={sorted(self.values)!r})"


class TimelinePlayer:
    def __init__(self, timeline: Timeline) -> None:
        self.timeline = timeline
        self._event_cursor = 0.0

    # -- params ---------------------------------------------------------
    def _env(self, t: float) -> dict:
        tl = self.timeline
        env = {k: float(v) for k, v in tl.params.items()}
        dur = tl.duration_ms
        env["k"] = (t / dur) if dur else 0.0
        env["t"] = float(t)
        return env

    def _value(self, v, env):
        if isinstance(v, str):
            return evaluate(v, env)
        if isinstance(v, (list, tuple)):
            return [self._value(x, env) for x in v]
        return v

    # -- key tracks -----------------------------------------------------
    def _sample_keys(self, keys: list, t: float, env) -> dict:
        if not keys:
            return {}
        if t <= keys[0]["t"]:
            chosen, nxt, u = keys[0], None, 0.0
        elif t >= keys[-1]["t"]:
            chosen, nxt, u = keys[-1], None, 0.0
        else:
            chosen, nxt, u = keys[-1], None, 0.0
            for a, b in zip(keys, keys[1:]):
                if a["t"] <= t <= b["t"]:
                    span = b["t"] - a["t"]
                    u = 0.0 if span == 0 else (t - a["t"]) / span
                    u = _EASE.get(a.get("ease", "linear"), _EASE["linear"])(u)
                    chosen, nxt = a, b
                    break
        # A key is a snapshot: its expressions resolve against the key's own
        # time (k/t bound to that key), then snapshots interpolate numerically.
        def key_env(key):
            e = self._env(float(key["t"]))
            e.update({k: v for k, v in env.items() if k not in ("k", "t")})
            return e

        out = {}
        for field in set(chosen) | (set(nxt) if nxt else set()):
            if field in _SKIP_FIELDS or field == "pose" or field == "look_at":
                if field in chosen and field not in ("t", "ease"):
                    out[field] = chosen[field]
                continue
            va = self._value(chosen.get(field), key_env(chosen)) if field in chosen else None
            if nxt is None or field not in nxt:
                if va is not None:
                    out[field] = va
                continue
            vb = self._value(nxt[field], key_env(nxt))
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                out[field] = va + (vb - va) * u
            elif isinstance(va, list) and isinstance(vb, list) and len(va) == len(vb) and \
                    all(isinstance(x, (int, float)) for x in va + vb):
                out[field] = [x + (y - x) * u for x, y in zip(va, vb)]
            else:
                out[field] = va
        return out

    # -- shots ----------------------------------------------------------
    def shot_at(self, t: float):
        """(index, shot) for timed shot lists; (None, None) when shots carry no durations."""
        acc = 0.0
        for i, shot in enumerate(self.timeline.shots):
            d = shot.get("duration_ms")
            if d is None:
                return None, None
            if t < acc + d:
                return i, shot
            acc += d
        if self.timeline.shots:
            return len(self.timeline.shots) - 1, self.timeline.shots[-1]
        return None, None

    # -- main entry -----------------------------------------------------
    def sample(self, t: float) -> Sample:
        tl = self.timeline
        t = max(0.0, float(t))
        env = self._env(t)
        values: dict[str, Any] = {}
        active: dict[str, list] = {}
        for name, track in tl.tracks.items():
            kind = name.split(":")[0]
            if kind in ("camera", "light", "actor", "decal"):
                values[name] = self._sample_keys(track, t, env)
            else:
                on = []
                for clip in track:
                    start = clip.get("start", clip.get("t", 0.0))
                    end = clip.get("end")
                    if t >= start and (end is None or t < end):
                        on.append(clip)
                active[name] = on
        idx, shot = self.shot_at(t)
        return Sample(t, values, active, shot, idx)

    def events_between(self, t0: float, t1: float) -> list:
        """Event clips whose start falls in (t0, t1], in timeline order."""
        out = []
        for track in self.timeline.tracks.get("event", []):
            start = track.get("start", track.get("t", 0.0))
            if t0 < start <= t1:
                out.append(track)
        return out

    def seek_events(self, t: float) -> list:
        """Fire-once event draining for players: events in (cursor, t]."""
        out = self.events_between(self._event_cursor, t)
        self._event_cursor = float(t)
        return out

    def reset_events(self) -> None:
        self._event_cursor = 0.0
