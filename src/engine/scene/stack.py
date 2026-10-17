"""SceneStack: the explicit replacement for stage flags and mode switches (§6.2).

Semantics
---------
* ``push(scene)``: the new scene runs on top. The scene below receives
  ``on_pause`` unless the new scene is an **overlay** (then it keeps drawing,
  and keeps updating only if the overlay sets ``passthrough_update``).
* ``pop()``: the top scene exits; the scene it had paused resumes.
* ``replace(scene)``: the top scene exits and ``scene`` takes its place; the
  scene below is paused/resumed only if its state actually changes.
* ``clear_to(scene)``: every scene exits (top first), then ``scene`` is pushed.

Mutations requested from inside a hook (``handle``/``update``/``draw``/… —
the usual place for them) are **deferred** until the current dispatch
finishes, so the frame that asked for the change completes against a stable
stack. Outside a dispatch they apply immediately. ``flush()`` applies pending
operations explicitly (hosts call it once per frame after their own dispatch).

Every structural change is appended to ``trace`` (a list of one-line strings
such as ``"push MENU"``) and, when a log is attached, written to the ``scene``
log channel. The trace is the Phase 2 oracle (``tests/data/*_scene_trace.txt``).

``transition`` arguments are accepted and recorded (``"push GAME via fade"``)
but not rendered by the stack: the host owns the pixels of a transition until
the render queue exists (Phase 6).
"""
from __future__ import annotations

from collections import deque
from typing import Any, Callable, Iterable

from .scene import Scene

__all__ = ["SceneStack"]


class _Entry:
    __slots__ = ("scene", "paused")

    def __init__(self, scene: Scene) -> None:
        self.scene = scene
        self.paused = False


class SceneStack:
    def __init__(self, ctx: Any = None, log: Any = None, trace_limit: int = 4096) -> None:
        self.ctx = ctx
        self.log = log
        self.trace: list[str] = []
        self.trace_limit = int(trace_limit)
        self.transition: Any = None            # last transition object requested, for the host
        self._entries: list[_Entry] = []
        self._pending: deque[Callable[[], None]] = deque()
        self._dispatching = 0

    # -- inspection ----------------------------------------------------------
    @property
    def top(self) -> Scene | None:
        return self._entries[-1].scene if self._entries else None

    @property
    def scenes(self) -> tuple[Scene, ...]:
        return tuple(e.scene for e in self._entries)

    def names(self) -> list[str]:
        return [e.scene.name for e in self._entries]

    def is_paused(self, scene: Scene) -> bool:
        for e in self._entries:
            if e.scene is scene:
                return e.paused
        raise ValueError(f"{scene!r} is not on the stack")

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, scene: object) -> bool:
        return any(e.scene is scene for e in self._entries)

    @property
    def pending(self) -> int:
        """Number of deferred mutations waiting for ``flush()``."""
        return len(self._pending)

    # -- mutations -----------------------------------------------------------
    def push(self, scene: Scene, transition: Any = None) -> None:
        self._request(lambda: self._push(scene, transition))

    def pop(self, transition: Any = None) -> None:
        self._request(lambda: self._pop(transition))

    def replace(self, scene: Scene, transition: Any = None) -> None:
        self._request(lambda: self._replace(scene, transition))

    def clear_to(self, scene: Scene, transition: Any = None) -> None:
        self._request(lambda: self._clear_to(scene, transition))

    def clear(self) -> None:
        """Exit every scene (top first). Used by hosts on shutdown."""
        self._request(self._clear)

    def flush(self) -> int:
        """Apply deferred mutations. Returns how many were applied."""
        if self._dispatching:
            return 0
        n = 0
        while self._pending:
            self._pending.popleft()()
            n += 1
        return n

    def _request(self, op: Callable[[], None]) -> None:
        if self._dispatching:
            self._pending.append(op)
        else:
            self._pending.append(op)
            self.flush()

    # -- primitive operations (never called during a dispatch) -----------------
    def _attach(self, scene: Scene) -> None:
        if scene in self:
            raise ValueError(f"{scene!r} is already on the stack")
        if scene.stack is not None and scene.stack is not self:
            raise ValueError(f"{scene!r} belongs to another stack")
        scene.stack = self

    def _push(self, scene: Scene, transition: Any) -> None:
        self._attach(scene)
        below = self._entries[-1] if self._entries else None
        if below is not None and not scene.overlay and not below.paused:
            below.paused = True
            below.scene.on_pause(self.ctx)
        self._entries.append(_Entry(scene))
        self.transition = transition
        self._record("push", scene, transition)
        scene.on_enter(self.ctx)

    def _pop(self, transition: Any) -> Scene | None:
        if not self._entries:
            return None
        entry = self._entries.pop()
        self.transition = transition
        self._record("pop", entry.scene, transition)
        entry.scene.on_exit(self.ctx)
        entry.scene.stack = None
        # The scene now on top is covered by nothing, so a paused one resumes.
        top = self._entries[-1] if self._entries else None
        if top is not None and top.paused:
            top.paused = False
            top.scene.on_resume(self.ctx)
        return entry.scene

    def _replace(self, scene: Scene, transition: Any) -> None:
        self._attach(scene)
        self.transition = transition
        if self._entries:
            old = self._entries.pop()
            self._record("replace", scene, transition, old.scene)
            old.scene.on_exit(self.ctx)
            old.scene.stack = None
        else:
            self._record("replace", scene, transition)
        below = self._entries[-1] if self._entries else None
        if below is not None:
            want_paused = not scene.overlay
            if want_paused and not below.paused:
                below.paused = True
                below.scene.on_pause(self.ctx)
            elif not want_paused and below.paused:
                below.paused = False
                below.scene.on_resume(self.ctx)
        self._entries.append(_Entry(scene))
        scene.on_enter(self.ctx)

    def _clear(self) -> None:
        while self._entries:
            entry = self._entries.pop()
            self._record("pop", entry.scene, None)
            entry.scene.on_exit(self.ctx)
            entry.scene.stack = None

    def _clear_to(self, scene: Scene, transition: Any) -> None:
        self._clear()
        self._push(scene, transition)

    # -- dispatch ------------------------------------------------------------
    def _active(self, for_update: bool) -> list[Scene]:
        """Scenes that take part in this frame, bottom-most first.

        Drawing: the top scene and every scene it reveals through overlays.
        Updating: the same, but an overlay only lets the scenes below update
        when it sets ``passthrough_update``.
        """
        out: list[Scene] = []
        i = len(self._entries) - 1
        while i >= 0:
            s = self._entries[i].scene
            out.append(s)
            if not s.overlay or (for_update and not s.passthrough_update):
                break
            i -= 1
        out.reverse()
        return out

    def handle(self, action_events: Iterable[Any]) -> bool:
        top = self.top
        if top is None:
            return False
        self._dispatching += 1
        try:
            return bool(top.handle(self.ctx, action_events))
        finally:
            self._dispatching -= 1
            self.flush()

    def fixed_update(self, dt: float) -> None:
        self._dispatching += 1
        try:
            for s in self._active(for_update=True):
                s.fixed_update(self.ctx, dt)
        finally:
            self._dispatching -= 1
            self.flush()

    def update(self, dt_real: float) -> None:
        self._dispatching += 1
        try:
            for s in self._active(for_update=True):
                s.update(self.ctx, dt_real)
        finally:
            self._dispatching -= 1
            self.flush()

    def draw(self, alpha: float = 1.0) -> None:
        self._dispatching += 1
        try:
            for s in self._active(for_update=False):
                s.draw(self.ctx, alpha)
        finally:
            self._dispatching -= 1
            self.flush()

    # -- trace -----------------------------------------------------------------
    def _record(self, op: str, scene: Scene, transition: Any, old: Scene | None = None) -> None:
        line = f"{op} {scene.name}"
        if old is not None:
            line = f"{op} {old.name} -> {scene.name}"
        if transition is not None:
            line += f" via {getattr(transition, 'name', transition)}"
        self.trace.append(line)
        if len(self.trace) > self.trace_limit:
            del self.trace[: len(self.trace) - self.trace_limit]
        if self.log is not None:
            self.log.info("scene", line)

    def trace_text(self) -> str:
        return "\n".join(self.trace) + ("\n" if self.trace else "")
