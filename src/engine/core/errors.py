"""Engine exceptions with context, and the crash-report writer (§6.1, §6.23)."""
from __future__ import annotations

import datetime as _dt
import traceback
from pathlib import Path
from typing import Any

__all__ = ["AEError", "AssetError", "TimelineError", "SchemaError", "write_crash_report"]


class AEError(Exception):
    """Base engine error. ``context`` carries ids (asset, timeline+t, entity...)."""

    def __init__(self, message: str, **context: Any) -> None:
        self.context = context
        ctx = ", ".join(f"{k}={v!r}" for k, v in sorted(context.items()))
        super().__init__(f"{message} [{ctx}]" if ctx else message)


class AssetError(AEError):
    pass


class TimelineError(AEError):
    pass


class SchemaError(AEError):
    pass


def write_crash_report(directory: str | Path, exc: BaseException, *, log_lines: list[str] | None = None,
                       extra: dict[str, Any] | None = None, screenshot=None, now: _dt.datetime | None = None) -> Path:
    """Write ``<dir>/<timestamp>.txt`` (+ ``.png`` if a pygame Surface is given)."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    ts = (now or _dt.datetime.now()).strftime("%Y%m%d-%H%M%S-%f")
    path = d / f"{ts}.txt"
    parts = ["RPE6 CRASH REPORT", f"time: {ts}", f"exception: {type(exc).__name__}: {exc}", ""]
    for k, v in sorted((extra or {}).items()):
        parts.append(f"{k}: {v}")
    parts += ["", "--- traceback ---", "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
              "--- last log lines ---", *(log_lines or [])[-200:]]
    path.write_text("\n".join(parts) + "\n", encoding="utf-8", newline="\n")
    if screenshot is not None:
        try:
            import pygame
            pygame.image.save(screenshot, str(path.with_suffix(".png")))
        except Exception as e:  # noqa: BLE001 - the report itself must survive
            with path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(f"(screenshot failed: {e!r})\n")
    return path
