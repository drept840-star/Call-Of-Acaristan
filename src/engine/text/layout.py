"""Text layout: measure, wrap, fit, ellipsis (§6.12).

The one rule: overflow cannot happen silently. ``check_fit`` logs a warning once
per site on the ``text`` channel, and ``draw_line`` outlines the box in red when
``DEV`` - a widget migrated in Phase 4 uses these, so a too-long string is a
visible bug in dev instead of a mystery in a screenshot. The red outline is
dev-only (``DEV`` is false in a frozen build); warnings always log.

All functions are pure pygame-free math on a ``pygame.font.Font`` so they run
headless.
"""
from __future__ import annotations

import sys

import pygame

from engine.core.log import get_log

__all__ = ["check_fit", "draw_line", "ellipsize", "fits", "measure", "wrap_lines"]

# Not a frozen build: show the dev overflow outline. Warnings log either way.
# (Deliberately not in __all__ - a dev knob, not engine API.)
DEV = not bool(getattr(sys, "frozen", False))

_OVERFLOW_COLOR = (255, 0, 0)


def measure(font: pygame.font.Font, text: str) -> tuple[int, int]:
    """Pixel size of ``text`` in ``font`` (same as ``font.size``, named for readability)."""
    return font.size(text)


def wrap_lines(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    """Greedy word wrap; a word wider than ``max_width`` is hard-split by glyph width."""
    if max_width <= 0:
        return [text]
    lines: list[str] = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            cand = word if not cur else f"{cur} {word}"
            if measure(font, cand)[0] <= max_width:
                cur = cand
                continue
            if cur:
                lines.append(cur)
                cur = ""
            while measure(font, word)[0] > max_width and len(word) > 1:
                lo, hi = 1, len(word)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if measure(font, word[:mid])[0] <= max_width:
                        lo = mid
                    else:
                        hi = mid - 1
                lines.append(word[:lo])
                word = word[lo:]
            cur = word
        lines.append(cur)
    return lines


def ellipsize(font: pygame.font.Font, text: str, max_width: int, mark: str = "\u2026") -> str:
    """Longest prefix of ``text`` that fits in ``max_width`` with ``mark`` appended."""
    if measure(font, text)[0] <= max_width:
        return text
    mark_w = measure(font, mark)[0]
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if measure(font, text[:mid])[0] + mark_w <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + mark


def fits(font: pygame.font.Font, text: str, width: int, height: int | None = None) -> bool:
    """True when ``text`` fits in (width, height); wrapped when ``height`` is given."""
    lines = [text] if height is None else wrap_lines(font, text, width)
    if any(measure(font, ln)[0] > width for ln in lines):
        return False
    if height is not None and font.get_linesize() * len(lines) > height:
        return False
    return True


def check_fit(font: pygame.font.Font, text: str, width: int, height: int | None = None,
              *, key: str | None = None) -> bool:
    """``fits`` + a warn-once on the ``text`` channel when it does not."""
    ok = fits(font, text, width, height)
    if not ok:
        w, h = measure(font, text)
        get_log().warn_once("text", key or f"fit:{text[:32]}",
                            f"text overflow ({w}x{h}px in {width}x{height} box): {text[:60]!r}")
    return ok


def draw_line(surf: pygame.Surface, font: pygame.font.Font, text: str, pos: tuple[int, int],
              color: tuple[int, int, int], *, width: int | None = None, height: int | None = None,
              key: str | None = None, align: str = "left") -> pygame.Rect:
    """Blit one line at ``pos``; with ``width`` given, overflow warns and (dev) outlines red."""
    img = font.render(text, True, color)
    rect = img.get_rect()
    if align == "center":
        rect.midtop = pos
    elif align == "right":
        rect.topright = pos
    else:
        rect.topleft = pos
    if width is not None and not check_fit(font, text, width, height, key=key) and DEV:
        outline = pygame.Rect(rect.left, rect.top, width, height or rect.height)
        pygame.draw.rect(surf, _OVERFLOW_COLOR, outline, 1)
    surf.blit(img, rect)
    return rect
