"""engine.world.entity - ``EntityId`` and ``World`` storage (RPE6 §6.4).

Not an archetype ECS: components live in per-type dicts keyed by ``EntityId``
(insertion-ordered, so every query walks entities in spawn order and a replay is
deterministic). Despawns are deferred to ``flush()`` (end of the POST phase) so a
system may despawn while iterating.

Views: a legacy object can stand in for a component through ``add(eid, view, kind=Transform)``
- the view must expose the component's fields as attributes. ``get``/``query`` return the
view itself, so new systems read the old object's state without copying it (§6.4
migration path step 1).
"""
from __future__ import annotations

from typing import Any, Iterator

from engine.core import SchemaError

from ._component import component_type, fields_of, is_component, to_dict

__all__ = ["EntityId", "World", "WorldError"]

EntityId = int


class WorldError(SchemaError):
    """Structural misuse of the world (unknown entity, read-only phase, unregistered kind)."""


class World:
    def __init__(self) -> None:
        self._next: int = 1
        self._entities: dict[EntityId, dict[type, Any]] = {}
        self._by_type: dict[type, dict[EntityId, Any]] = {}
        self._pending: list[EntityId] = []
        self._readonly: bool = False
        self.events: list[Any] = []  # emitted during a step, drained by the POST flush

    # ── entities ───────────────────────────────────────────────────────────
    def spawn(self, *comps: Any) -> EntityId:
        self._check_writable("spawn")
        eid = self._next
        self._next += 1
        self._entities[eid] = {}
        for c in comps:
            self.add(eid, c)
        return eid

    def despawn(self, eid: EntityId) -> None:
        """Deferred: the entity disappears at the next ``flush()``."""
        self._check_writable("despawn")
        if eid in self._entities and eid not in self._pending:
            self._pending.append(eid)

    def despawn_now(self, eid: EntityId) -> None:
        self._check_writable("despawn_now")
        comps = self._entities.pop(eid, None)
        if comps is None:
            return
        for kind in comps:
            table = self._by_type.get(kind)
            if table is not None:
                table.pop(eid, None)

    def flush(self) -> int:
        """Apply deferred despawns and drop emitted events; returns the number despawned."""
        n = 0
        while self._pending:
            eid = self._pending.pop(0)
            if eid in self._entities:
                self.despawn_now(eid)
                n += 1
        self.events.clear()
        return n

    def alive(self, eid: EntityId) -> bool:
        return eid in self._entities and eid not in self._pending

    def entities(self) -> list[EntityId]:
        return list(self._entities)

    def pending_despawns(self) -> tuple[EntityId, ...]:
        return tuple(self._pending)

    def __len__(self) -> int:
        return len(self._entities)

    def __contains__(self, eid: object) -> bool:
        return eid in self._entities

    # ── components ─────────────────────────────────────────────────────────
    def add(self, eid: EntityId, comp: Any, kind: type | None = None) -> Any:
        """Attach ``comp`` (a component instance, or a view when ``kind`` is given)."""
        self._check_writable("add")
        comps = self._entity(eid)
        k = kind or getattr(comp, "__ae_view_of__", None) or type(comp)
        if not is_component(k):
            raise WorldError(f"{k.__name__ if isinstance(k, type) else k!r} is not a registered component")
        if kind is not None and not isinstance(comp, kind):
            missing = [f.name for f in fields_of(kind) if not hasattr(comp, f.name)]
            if missing:
                raise WorldError(f"view for {kind.__name__} lacks field(s) {missing}")
            try:
                comp.__ae_view_of__ = kind
            except AttributeError:
                pass
        comps[k] = comp
        self._by_type.setdefault(k, {})[eid] = comp
        return comp

    def remove(self, eid: EntityId, kind: type) -> Any:
        self._check_writable("remove")
        comps = self._entity(eid)
        comp = comps.pop(kind, None)
        table = self._by_type.get(kind)
        if table is not None:
            table.pop(eid, None)
        return comp

    def get(self, eid: EntityId, kind: type, default: Any = None) -> Any:
        comps = self._entities.get(eid)
        if comps is None:
            return default
        return comps.get(kind, default)

    def require(self, eid: EntityId, kind: type) -> Any:
        comp = self.get(eid, kind)
        if comp is None:
            raise WorldError(f"entity {eid} has no {kind.__name__}")
        return comp

    def has(self, eid: EntityId, *kinds: type) -> bool:
        comps = self._entities.get(eid)
        return comps is not None and all(k in comps for k in kinds)

    def components(self, eid: EntityId) -> tuple[Any, ...]:
        return tuple(self._entity(eid).values())

    def kinds(self, eid: EntityId) -> tuple[type, ...]:
        return tuple(self._entity(eid).keys())

    # ── queries ────────────────────────────────────────────────────────────
    def query(self, *kinds: type) -> Iterator[tuple[EntityId, tuple[Any, ...]]]:
        """Yield ``(eid, (c1, c2, ...))`` for every live entity owning all ``kinds``, in spawn order.

        Snapshot semantics: entities spawned during iteration are not visited; entities
        despawned (deferred) during iteration are skipped from then on.
        """
        if not kinds:
            raise WorldError("query needs at least one component kind")
        for k in kinds:
            if not is_component(k):
                raise WorldError(f"{getattr(k, '__name__', k)!r} is not a registered component")
        lead = kinds[0]
        table = self._by_type.get(lead)
        if not table:
            return
        for eid in list(table):
            comps = self._entities.get(eid)
            if comps is None or eid in self._pending:
                continue
            try:
                yield eid, tuple(comps[k] for k in kinds)
            except KeyError:
                continue

    def first(self, *kinds: type) -> tuple[EntityId, tuple[Any, ...]] | None:
        for item in self.query(*kinds):
            return item
        return None

    def count(self, kind: type | None = None) -> int:
        if kind is None:
            return len(self._entities)
        return sum(1 for eid in self._by_type.get(kind, ()) if eid not in self._pending)

    # ── read-only guard (RENDER_SUBMIT phase, debug mode) ──────────────────
    def set_readonly(self, flag: bool) -> None:
        self._readonly = bool(flag)

    @property
    def readonly(self) -> bool:
        return self._readonly

    # ── events ─────────────────────────────────────────────────────────────
    def emit(self, event: Any) -> None:
        self.events.append(event)

    # ── inspection ─────────────────────────────────────────────────────────
    def dump(self) -> dict[str, Any]:
        """Component census: ``{"entities": n, "components": {name: {"count", "version", "fields"}}}``."""
        comps: dict[str, Any] = {}
        for kind, table in self._by_type.items():
            n = sum(1 for eid in table if eid not in self._pending)
            if n == 0:
                continue
            comps[kind.__name__] = {
                "count": n,
                "version": int(getattr(kind, "__ae_version__", 1)),
                "fields": [f.name for f in fields_of(kind)],
            }
        return {"entities": self.count(), "pending_despawns": len(self._pending),
                "components": dict(sorted(comps.items()))}

    def dump_entity(self, eid: EntityId) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for kind, comp in self._entity(eid).items():
            try:
                out[kind.__name__] = to_dict(comp)
            except Exception as e:  # a view whose owner vanished must not kill the inspector
                out[kind.__name__] = {"<error>": repr(e)}
        return out

    def by_name(self, name: str) -> type:
        """Component class for a registry name (prefabs, console)."""
        return component_type(name)

    # ── internals ──────────────────────────────────────────────────────────
    def _entity(self, eid: EntityId) -> dict[type, Any]:
        try:
            return self._entities[eid]
        except KeyError:
            raise WorldError(f"unknown entity {eid}") from None

    def _check_writable(self, op: str) -> None:
        if self._readonly:
            raise WorldError(f"world.{op}() during a read-only phase (RENDER_SUBMIT)")
