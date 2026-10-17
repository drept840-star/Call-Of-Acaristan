"""Typed event bus (§6.3). Events are any objects; subscription is by type.

``emit`` queues until :meth:`flush` (end of sim step); ``emit_now`` delivers
synchronously (UI only). Subscriptions may carry a ``scope`` token so a scene
or world can drop all of its handlers at once (no leaks).
"""
from __future__ import annotations

from collections import deque
from typing import Any, Callable

__all__ = ["EventBus", "Subscription"]


class Subscription:
    __slots__ = ("etype", "fn", "scope", "active")

    def __init__(self, etype: type, fn: Callable[[Any], None], scope: object | None) -> None:
        self.etype, self.fn, self.scope, self.active = etype, fn, scope, True


class EventBus:
    def __init__(self, history: int = 256) -> None:
        self._subs: dict[type, list[Subscription]] = {}
        self._queue: deque = deque()
        self._log: deque = deque(maxlen=history)

    def subscribe(self, etype: type, fn: Callable[[Any], None], scope: object | None = None) -> Subscription:
        sub = Subscription(etype, fn, scope)
        self._subs.setdefault(etype, []).append(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        sub.active = False
        lst = self._subs.get(sub.etype, [])
        if sub in lst:
            lst.remove(sub)

    def unsubscribe_scope(self, scope: object) -> int:
        n = 0
        for lst in self._subs.values():
            for sub in [s for s in lst if s.scope is scope]:
                sub.active = False
                lst.remove(sub)
                n += 1
        return n

    def emit(self, event: Any) -> None:
        self._queue.append(event)

    def emit_now(self, event: Any) -> None:
        self._deliver(event)

    def flush(self, max_events: int = 10_000) -> int:
        """Deliver queued events (including ones emitted during delivery)."""
        n = 0
        while self._queue and n < max_events:
            self._deliver(self._queue.popleft())
            n += 1
        return n

    def pending(self) -> int:
        return len(self._queue)

    def tail(self, n: int = 50) -> list:
        return list(self._log)[-n:]

    def _deliver(self, event: Any) -> None:
        self._log.append(event)
        for cls in type(event).__mro__:
            for sub in list(self._subs.get(cls, ())):
                if sub.active:
                    sub.fn(event)
