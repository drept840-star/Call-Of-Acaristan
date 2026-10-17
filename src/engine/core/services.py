"""Explicit service registry (§6.1): no magic globals, clear errors."""
from __future__ import annotations

from typing import Any

__all__ = ["Services", "ServiceMissing"]


class ServiceMissing(LookupError):
    pass


class Services:
    def __init__(self) -> None:
        self._items: dict[str, Any] = {}

    def register(self, name: str, obj: Any, replace: bool = False) -> Any:
        if name in self._items and not replace:
            raise ValueError(f"service {name!r} already registered")
        self._items[name] = obj
        return obj

    def get(self, name: str) -> Any:
        try:
            return self._items[name]
        except KeyError:
            raise ServiceMissing(f"service {name!r} is not registered (registered: {sorted(self._items)}); "
                                 "was App.boot() called?") from None

    def has(self, name: str) -> bool:
        return name in self._items

    def names(self) -> list[str]:
        return sorted(self._items)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return self.get(name)
