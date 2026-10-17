"""game.world.legacy - strangler bridge between the pre-ECS objects and ``engine.world`` (RPE6 §6.4 step 1).

Every legacy gameplay object that lives in ``STATE`` gets an entity whose standard
components are *views* onto the object's own fields - nothing is copied, nothing
moves, so the legacy update paths keep full authority (replay parity) while new
systems and tools (``tools/ae_dump_components.py``, the inspector) already see
entities with declared components.

Roster sync runs in the ``PRE`` phase: objects that appeared in ``STATE`` since the
last step are spawned, objects that vanished are despawned (deferred to the POST
flush). Identity is the Python object; dead ``Enemy`` instances removed from
``STATE.enemies`` leave the world the same frame.

Owner module for the module-level world/scheduler: access through
``import game.world as _gw; _gw.world()``.
"""
from __future__ import annotations

from typing import Any

from typing import Callable

from engine.world import (
    AIBrain, Collider, Faction, Health, Label, LegacyRef, Lifetime, POST, PRE, SIM, FunctionSystem, Scheduler, System,
    Tags, Transform, WalkCycle, World,
)

__all__ = [
    "EnemyTransformView", "EnemyHealthView", "EnemyBrainView", "PlayerTransformView", "PlayerHealthView",
    "PointView", "ListPickupView", "FireZoneLifeView", "LegacyRoster", "make_roster_system", "LegacyMissionSystem",
]


# ── views (component fields as properties over the legacy object) ─────────────
class _RectTransformView:
    """Transform over a ``pygame.Rect``-owning object (centre = position)."""
    __slots__ = ("_o", "__ae_view_of__")

    def __init__(self, obj: Any) -> None:
        self._o = obj
        self.__ae_view_of__ = Transform

    @property
    def x(self) -> float:
        return float(self._o.rect.centerx)

    @x.setter
    def x(self, v: float) -> None:
        self._o.rect.centerx = int(v)

    @property
    def y(self) -> float:
        return float(self._o.rect.centery)

    @y.setter
    def y(self, v: float) -> None:
        self._o.rect.centery = int(v)

    @property
    def angle(self) -> float:
        return float(getattr(self._o, "angle", 0.0))

    @angle.setter
    def angle(self, v: float) -> None:
        self._o.angle = v

    # No fixed-step interpolation in the legacy loop: previous == current.
    @property
    def prev_x(self) -> float:
        return self.x

    @property
    def prev_y(self) -> float:
        return self.y

    def interp(self, alpha: float) -> tuple[float, float]:
        return self.x, self.y


class EnemyTransformView(_RectTransformView):
    pass


class PlayerTransformView(_RectTransformView):
    pass


class DoorTransformView(_RectTransformView):
    pass


class EnemyHealthView:
    """Health over ``Enemy.hp``; ``max`` is the hp seen when the entity was registered."""
    __slots__ = ("_o", "max", "__ae_view_of__")

    def __init__(self, enemy: Any) -> None:
        self._o = enemy
        self.max = float(enemy.hp)
        self.__ae_view_of__ = Health

    @property
    def hp(self) -> float:
        return float(self._o.hp)

    @hp.setter
    def hp(self, v: float) -> None:
        self._o.hp = v

    @property
    def alive(self) -> bool:
        return self._o.hp > 0

    @property
    def fraction(self) -> float:
        return 0.0 if self.max <= 0 else max(0.0, min(1.0, self.hp / self.max))


class PlayerHealthView:
    __slots__ = ("_o", "__ae_view_of__")

    def __init__(self, player: Any) -> None:
        self._o = player
        self.__ae_view_of__ = Health

    @property
    def hp(self) -> float:
        return float(self._o.hp)

    @hp.setter
    def hp(self, v: float) -> None:
        self._o.hp = v

    @property
    def max(self) -> float:
        return float(getattr(self._o, "max_hp", 100))

    @property
    def alive(self) -> bool:
        return self._o.hp > 0

    @property
    def fraction(self) -> float:
        m = self.max
        return 0.0 if m <= 0 else max(0.0, min(1.0, self.hp / m))


class EnemyBrainView:
    """AIBrain over ``Enemy.state`` (IDLE/PATROL/CHASE/ATTACK/SEARCH...)."""
    __slots__ = ("_o", "profile", "__ae_view_of__")

    def __init__(self, enemy: Any, profile: str = "legacy") -> None:
        self._o = enemy
        self.profile = profile
        self.__ae_view_of__ = AIBrain

    @property
    def state(self) -> str:
        return str(self._o.state)

    @state.setter
    def state(self, v: str) -> None:
        self._o.state = v


class PointView:
    """Transform over an object with float ``x``/``y`` (+ optional ``angle``): corpses, fire zones, Maru."""
    __slots__ = ("_o", "_getter", "__ae_view_of__")

    def __init__(self, obj: Any) -> None:
        self._o = obj
        self._getter = obj.__getitem__ if isinstance(obj, dict) else None
        self.__ae_view_of__ = Transform

    def _g(self, name: str, default: float = 0.0) -> float:
        if self._getter is not None:
            return float(self._o.get(name, default))
        return float(getattr(self._o, name, default))

    def _s(self, name: str, v: float) -> None:
        if self._getter is not None:
            self._o[name] = v
        else:
            setattr(self._o, name, v)

    x = property(lambda s: s._g("x"), lambda s, v: s._s("x", v))
    y = property(lambda s: s._g("y"), lambda s, v: s._s("y", v))
    angle = property(lambda s: s._g("angle"), lambda s, v: s._s("angle", v))
    prev_x = property(lambda s: s._g("x"))
    prev_y = property(lambda s: s._g("y"))

    def interp(self, alpha: float) -> tuple[float, float]:
        return self.x, self.y


class ListPickupView:
    """Transform over the legacy pickup record ``[x, y, kind, ...]``."""
    __slots__ = ("_o", "__ae_view_of__")

    def __init__(self, rec: list) -> None:
        self._o = rec
        self.__ae_view_of__ = Transform

    x = property(lambda s: float(s._o[0]), lambda s, v: s._o.__setitem__(0, v))
    y = property(lambda s: float(s._o[1]), lambda s, v: s._o.__setitem__(1, v))
    angle = property(lambda s: 0.0)
    prev_x = property(lambda s: float(s._o[0]))
    prev_y = property(lambda s: float(s._o[1]))

    def interp(self, alpha: float) -> tuple[float, float]:
        return self.x, self.y


class FireZoneLifeView:
    """Lifetime over ``FireZone.life`` (frames remaining)."""
    __slots__ = ("_o", "__ae_view_of__")

    def __init__(self, fz: Any) -> None:
        self._o = fz
        self.__ae_view_of__ = Lifetime

    remaining = property(lambda s: float(s._o.life), lambda s, v: setattr(s._o, "life", v))

    @property
    def expired(self) -> bool:
        return self._o.life <= 0


class _DictHealthView:
    __slots__ = ("_o", "__ae_view_of__")

    def __init__(self, d: dict) -> None:
        self._o = d
        self.__ae_view_of__ = Health

    hp = property(lambda s: float(s._o.get("hp", 0)), lambda s, v: s._o.__setitem__("hp", v))
    max = property(lambda s: float(s._o.get("max_hp", 0)))

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def fraction(self) -> float:
        m = self.max
        return 0.0 if m <= 0 else max(0.0, min(1.0, self.hp / m))


# ── roster sync ───────────────────────────────────────────────────────────────
class LegacyRoster:
    """Keeps one entity per live legacy object; call ``sync(state)`` once per step (PRE)."""

    def __init__(self, world: World) -> None:
        self.world = world
        self._eid_of: dict[int, int] = {}      # id(obj) -> eid
        self._obj_of: dict[int, Any] = {}      # eid -> obj (strong ref: keeps id() stable while registered)
        self._removed: set[int] = set()        # enemy eids that left STATE.enemies (kept until reset)
        self._enemy_eids: set[int] = set()     # entities registered through _spawn_enemy
        self._roster_ids: tuple[int, int] = (0, 0)  # (id(state.enemies), 0) -> reset detection
        self.spawned = 0
        self.despawned = 0
        self.resets = 0

    # registration ------------------------------------------------------------
    def eid_for(self, obj: Any) -> int | None:
        return self._eid_of.get(id(obj))

    def obj_for(self, eid: int) -> Any:
        return self._obj_of.get(eid)

    def _register(self, obj: Any, *comps: Any, views: tuple[tuple[Any, type], ...] = ()) -> int:
        eid = self.world.spawn(*comps)
        for view, kind in views:
            self.world.add(eid, view, kind=kind)
        self._eid_of[id(obj)] = eid
        self._obj_of[eid] = obj
        self.spawned += 1
        return eid

    def _spawn_enemy(self, e: Any) -> int:
        kind = type(e).__name__
        comps = [LegacyRef(uid=int(getattr(e, "uid", 0)), kind=kind), Faction("hostile"),
                 Collider(float(e.rect.w), float(e.rect.h))]
        walk = getattr(e, "walk", None)
        if isinstance(walk, WalkCycle):
            comps.append(walk)  # the Enemy's declared WalkCycle *is* the entity's component (one object)
        eid = self._register(
            e, *comps,
            views=((EnemyTransformView(e), Transform), (EnemyHealthView(e), Health), (EnemyBrainView(e), AIBrain)),
        )
        self._enemy_eids.add(eid)
        return eid

    def check_reset(self, state: Any) -> bool:
        """``STATE.enemies`` was rebound to another list: the mission (re)started, a stage rebuilt its
        world, or a helper swapped the list (``_spawn_m3_guards_once``, the smoke self-checks, wave
        code that builds a new list from the old one). Enemy entities whose objects are *not* in the
        new list are gone for good (including the ones tagged "removed"); objects still listed keep
        their entity and components. Other kinds (player, doors, pickups, corpses, fire zones) are not
        touched here - ``sync`` despawns them when they leave their own lists. The player object is
        deliberately not part of the key - it is (re)assigned at a different moment than the list."""
        enemies = getattr(state, "enemies", None)
        ids = (id(enemies), 0)
        if ids == self._roster_ids:
            return False
        first = self._roster_ids == (0, 0)
        self._roster_ids = ids
        if first:
            return False
        keep = {id(e) for e in (enemies or ())}
        for eid in list(self._enemy_eids):
            obj = self._obj_of.get(eid)
            if obj is not None and id(obj) in keep:
                continue
            self._eid_of.pop(id(obj), None)
            self._obj_of.pop(eid, None)
            self._enemy_eids.discard(eid)
            self._removed.discard(eid)
            self.world.despawn_now(eid)
            self.despawned += 1
        self.resets += 1
        return True

    def register_now(self, obj: Any, state: Any = None) -> int:
        """Entity for ``obj`` right away (missions attach components at spawn time, before the next PRE sync)."""
        if state is not None:
            self.check_reset(state)
        eid = self._eid_of.get(id(obj))
        if eid is not None:
            return eid
        if state is not None and obj is getattr(state, "player", None):
            return self._spawn_player(obj)
        if isinstance(obj, dict):
            return self._spawn_npc(obj, str(obj.get("name", "NPC")))
        if isinstance(obj, list):
            return self._spawn_pickup(obj)
        if hasattr(obj, "rect") and hasattr(obj, "hp") and hasattr(obj, "state"):
            return self._spawn_enemy(obj)
        if hasattr(obj, "rect") and hasattr(obj, "hp"):
            return self._spawn_player(obj)
        if hasattr(obj, "life") and hasattr(obj, "radius"):
            return self._spawn_fire_zone(obj)
        if hasattr(obj, "rect") and hasattr(obj, "anim_progress"):
            return self._spawn_door(obj)
        if hasattr(obj, "x") and hasattr(obj, "y"):
            return self._spawn_corpse(obj)
        raise TypeError(f"game.world: cannot bridge {type(obj).__name__}")

    def _spawn_door(self, d: Any) -> int:
        return self._register(d, LegacyRef(kind="Door"), Label(kind="door"),
                              Collider(float(d.rect.w), float(d.rect.h), solid=not bool(getattr(d, "collision_disabled", False))),
                              views=((DoorTransformView(d), Transform),))

    def _spawn_player(self, p: Any) -> int:
        return self._register(
            p,
            LegacyRef(uid=0, kind="Player"),
            Faction("player"),
            Collider(float(p.rect.w), float(p.rect.h)),
            views=((PlayerTransformView(p), Transform), (PlayerHealthView(p), Health)),
        )

    def _spawn_pickup(self, rec: list) -> int:
        kind = str(rec[2]) if len(rec) > 2 else ""
        return self._register(rec, LegacyRef(kind="Pickup"), Label(text=kind, kind="pickup"),
                              views=((ListPickupView(rec), Transform),))

    def _spawn_corpse(self, c: Any) -> int:
        return self._register(c, LegacyRef(kind="Corpse"), Label(kind="corpse"), views=((PointView(c), Transform),))

    def _spawn_fire_zone(self, fz: Any) -> int:
        return self._register(fz, LegacyRef(kind="FireZone"), Label(kind="fire_zone"),
                              Collider(radius=float(getattr(fz, "radius", 0.0)), solid=False),
                              views=((PointView(fz), Transform), (FireZoneLifeView(fz), Lifetime)))

    def _spawn_npc(self, d: dict, name: str) -> int:
        return self._register(d, LegacyRef(kind="NPC"), Faction("friendly"), Label(text=str(d.get("name", name)), kind="npc"),
                              views=((PointView(d), Transform), (_DictHealthView(d), Health)))

    # sync --------------------------------------------------------------------
    def sync(self, state: Any) -> None:
        self.check_reset(state)
        live: set[int] = set()
        player = getattr(state, "player", None)
        if player is not None:
            live.add(id(player))
            if id(player) not in self._eid_of:
                self._spawn_player(player)
        for e in getattr(state, "enemies", ()) or ():
            live.add(id(e))
            if id(e) not in self._eid_of:
                self._spawn_enemy(e)
        for rec in getattr(state, "pickups", ()) or ():
            if isinstance(rec, list) and len(rec) >= 2:
                live.add(id(rec))
                if id(rec) not in self._eid_of:
                    self._spawn_pickup(rec)
        for c in getattr(state, "corpses", ()) or ():
            live.add(id(c))
            if id(c) not in self._eid_of:
                self._spawn_corpse(c)
        for fz in getattr(state, "fire_zones", ()) or ():
            live.add(id(fz))
            if id(fz) not in self._eid_of:
                self._spawn_fire_zone(fz)
        for d in getattr(state, "doors", ()) or ():
            live.add(id(d))
            if id(d) not in self._eid_of:
                self._spawn_door(d)
        maru = getattr(state, "m5_maru", None)
        if isinstance(maru, dict):
            live.add(id(maru))
            if id(maru) not in self._eid_of:
                self._spawn_npc(maru, "MARU")
        # Vanished objects: transient kinds are despawned (deferred; the POST flush applies
        # it). Enemies are kept until the next mission reset - legacy code still holds
        # references to removed enemies (kill counting, squads, corpses) and their mission
        # components must survive that - they are tagged "removed" instead.
        gone = [oid for oid in self._eid_of if oid not in live]
        for oid in gone:
            eid = self._eid_of[oid]
            if eid in self._removed:
                continue
            if eid in self._enemy_eids:
                self._removed.add(eid)
                tags = self.world.get(eid, Tags)
                if tags is None:
                    self.world.add(eid, Tags({"removed"}))
                else:
                    tags.set.add("removed")
                continue
            self._eid_of.pop(oid, None)
            self._obj_of.pop(eid, None)
            self.world.despawn(eid)
            self.despawned += 1

    def removed_count(self) -> int:
        return len(self._removed)

    def clear(self) -> None:
        for eid in list(self._obj_of):
            self.world.despawn_now(eid)
        self._eid_of.clear()
        self._obj_of.clear()
        self._removed.clear()
        self._enemy_eids.clear()


def make_roster_system(roster: LegacyRoster, state: Any) -> FunctionSystem:
    """PRE-phase system (order -100) that mirrors ``state`` into ``roster.world``."""
    return FunctionSystem(lambda world, ctx, dt: roster.sync(state), name="legacy_roster", phase=PRE, order=-100,
                          writes=(LegacyRef, Transform, Health, AIBrain, Faction, Collider, Label, Lifetime, Tags,
                                  WalkCycle))


class LegacyMissionSystem(System):
    """SIM-phase host (order 0) for the per-mission legacy update (RPE6 §6.4 step 1, P5-M6).

    The legacy ``mN.game_update`` is still the simulation authority: movement, collision,
    combat, AI, interaction, pickups and props all run inside it and write through
    ``STATE``. Hosting it as a *declared* system makes the frame order the scheduler's
    truth - ``Scheduler.describe()`` and the component dump list it between the PRE
    roster sync and the POST flush, and new SIM systems order themselves before or after
    it with ``order``. ``host_step`` is the only entry point: it arms the callable for
    exactly one SIM pass, runs PRE -> SIM -> POST and returns the callable's result.
    Exceptions propagate unchanged (POST still runs, as the previous try/finally did).
    """

    name = "legacy_mission_update"
    phase = SIM
    order = 0

    def __init__(self) -> None:
        self._fn: Callable[[], Any] | None = None
        self._result: Any = None

    def run(self, world: World, ctx: Any, dt: float) -> None:
        fn, self._fn = self._fn, None
        if fn is not None:
            self._result = fn()

    def host_step(self, sched: Scheduler, ctx: Any, dt: float, fn: Callable[[], Any]) -> Any:
        sched.run_phase(PRE, ctx, dt)
        self._fn, self._result = fn, None
        try:
            sched.run_phase(SIM, ctx, dt)
        finally:
            self._fn = None
            sched.run_phase(POST, ctx, dt)
            sched.steps += 1
        result, self._result = self._result, None
        return result
