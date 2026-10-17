"""Structured logging with channels, a ring buffer and warn-once (§6.23)."""
from __future__ import annotations

import sys
from collections import deque

__all__ = ["CHANNELS", "LEVELS", "Log", "get_log"]

CHANNELS = ("core", "scene", "assets", "render", "render3d", "audio", "input", "world",
            "ai", "dialogue", "timeline", "save", "tools", "text", "ui")
LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}


class Log:
    def __init__(self, capacity: int = 200, echo_level: str = "warn", stream=None) -> None:
        self.lines: deque[str] = deque(maxlen=capacity)
        self.echo_level = LEVELS[echo_level]
        self.stream = stream
        self._once: set = set()

    def log(self, channel: str, level: str, msg: str) -> None:
        if channel not in CHANNELS:
            raise ValueError(f"unknown log channel {channel!r}; add it to engine.core.log.CHANNELS")
        line = f"[RPE6][{channel}] {level.upper()}: {msg}"
        self.lines.append(line)
        if LEVELS[level] >= self.echo_level:
            print(line, file=self.stream or sys.stderr)

    def debug(self, channel: str, msg: str) -> None:
        self.log(channel, "debug", msg)

    def info(self, channel: str, msg: str) -> None:
        self.log(channel, "info", msg)

    def warn(self, channel: str, msg: str) -> None:
        self.log(channel, "warn", msg)

    def error(self, channel: str, msg: str) -> None:
        self.log(channel, "error", msg)

    def warn_once(self, channel: str, key: str, msg: str) -> bool:
        """Warn the first time ``key`` is seen; return True if it was logged."""
        k = (channel, key)
        if k in self._once:
            return False
        self._once.add(k)
        self.warn(channel, msg)
        return True

    def tail(self, n: int = 50) -> list[str]:
        return list(self.lines)[-n:]


_DEFAULT: Log | None = None


def get_log() -> Log:
    """Process log used by tools and by App.current(); created lazily."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Log()
    return _DEFAULT
