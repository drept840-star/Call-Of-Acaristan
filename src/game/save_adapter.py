"""RPE6 Phase 9: game-side adapter between live state and ``engine.save``.

``capture()`` builds an ``ae.save/1`` snapshot from the live game: the
mission key, the scene stack summary, every JSON-primitive field on
``core.state.STATE``, the player rect/hp, live enemy component dumps
(``game.world``), and the RNG stream states (stdlib ``random`` + the
engine ``legacy`` stream).  ``restore()`` writes a snapshot back onto
*live* state: STATE fields, player, RNG states, and component fields of
entities that are still alive (views write through to legacy objects).
Entities that no longer exist are skipped -- mid-run resurrection stays
with the legacy checkpoint flow, which remains authoritative; snapshots
ride alongside it (see ``capture_m5_checkpoint``).

Floats in the state hash are quantised to 1e-4 by ``engine.save``; real
divergence is far above that, sub-quantum noise is benign.
"""
from __future__ import annotations

import json
import random
from typing import Any

from engine import save as _save
from core.state import STATE

__all__ = ["capture", "restore", "statehash", "capture_m5_checkpoint"]


def _jsonable(v: Any) -> bool:
    return v is None or isinstance(v, (bool, int, float, str)) or (
        isinstance(v, (list, tuple)) and all(_jsonable(x) for x in v)) or (
        isinstance(v, dict) and all(isinstance(k, str) and _jsonable(x) for k, x in v.items()))


def _rng_state_json(rng: random.Random) -> Any:
    def conv(x):
        if isinstance(x, tuple):
            return [conv(y) for y in x]
        return x
    return conv(rng.getstate())


def _rng_state_restore(rng: random.Random, data: Any) -> None:
    def conv(x):
        if isinstance(x, list):
            return tuple(conv(y) for y in x)
        return x
    rng.setstate(conv(data))


def _clean(v: Any) -> Any:
    """JSON-safe deep copy of ``v`` (tuples tagged), or None if not plain data.

    The copy matters: a snapshot must not alias live mutable state.  Tuples
    are encoded as ``{"$tuple": [...]}`` so restore can rebuild them exactly
    (game code and the replay oracle both distinguish tuple from list).
    """
    if isinstance(v, tuple):
        items = [_clean(x) for x in v]
        return None if any(x is None and v[i] is not None for i, x in enumerate(items)) else {"$tuple": items}
    if isinstance(v, list):
        items = [_clean(x) for x in v]
        return None if any(x is None and v[i] is not None for i, x in enumerate(items)) else items
    if isinstance(v, dict):
        out: dict[str, Any] = {}
        for k, x in v.items():
            if not isinstance(k, str):
                return None
            cx = _clean(x)
            if cx is None and x is not None:
                return None
            out[k] = cx
        return out
    if isinstance(v, (set, frozenset)):
        items = [_clean(x) for x in v]
        if any(x is None and v for x in items):
            return None
        return {"$set": sorted(items, key=repr)}
    try:
        return json.loads(json.dumps(v))
    except (TypeError, ValueError):
        return None


def _unclean(v: Any) -> Any:
    """Inverse of :func:`_clean` (rebuilds tuples, deep-copies the rest)."""
    if isinstance(v, dict) and set(v) == {"$tuple"} and isinstance(v["$tuple"], list):
        return tuple(_unclean(x) for x in v["$tuple"])
    if isinstance(v, dict) and set(v) == {"$set"} and isinstance(v["$set"], list):
        return set(_unclean(x) for x in v["$set"])
    if isinstance(v, dict):
        return {k: _unclean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_unclean(x) for x in v]
    return v


def _set_attr(obj: Any, name: str, value: Any) -> None:
    """setattr that does not materialise class defaults onto the instance.

    Restoring a captured class default onto an object that never had it as
    an instance attr would change the object's ``vars()`` (which the replay
    oracle canonicalises) without changing behaviour.  If the instance
    carries the attr, it is always written (resetting run-advanced values).
    """
    if name not in vars(obj):
        cls_val = getattr(type(obj), name, None)
        if cls_val is not None and type(cls_val) is type(value) and cls_val == value:
            return
    setattr(obj, name, value)


def _object_attrs(obj: Any) -> dict[str, Any]:
    """Plain-data attrs of a live object, private ones included.

    Enemy/player private timers (``_step_timer`` ...) are simulation state;
    non-data values (surfaces, callables, objects) are filtered by _clean.
    """
    out: dict[str, Any] = {}
    # dir(), not vars(): sim timers often live as class defaults until the
    # first assignment; both captures must see the same key set.
    for k in dir(obj):
        if k.startswith("__"):
            continue
        try:
            val = getattr(obj, k)
        except Exception:
            continue
        if callable(val):
            continue
        cv = _clean(val)
        if cv is not None:
            out[k] = cv
    return out


def _world_dump() -> dict:
    out: dict[str, Any] = {"enemies": []}
    try:
        import game.world as gw  # lazy: booted by game_core
        if gw.installed():
            w, roster = gw.world(), gw.roster()
        else:
            w = roster = None
    except Exception:
        w = roster = None
    for idx, e in enumerate(list(getattr(STATE, "enemies", []) or [])):
        entry: dict[str, Any] = {"idx": idx, "components": {}, "legacy": {}}
        if w is not None:
            eid = roster.eid_for(e)
            if eid is not None:
                entry["eid"] = int(eid)
                dump = _clean(w.dump_entity(eid))
                if dump:
                    entry["components"] = dump
        # Legacy objects still carry most sim state (Phase 5 views cover a
        # declared subset); snapshot their plain-data attrs too.
        entry["legacy"] = _object_attrs(e)
        out["enemies"].append(entry)
    return out


def _mission_modules(mission: str) -> list:
    """Loaded modules of the active mission's package (plain-data globals).

    Mission code keeps sim timers/flags in module globals; those are
    mission vars in everything but location, so they ride in the snapshot.
    """
    import sys
    num = "".join(ch for ch in str(mission) if ch.isdigit())
    if not num:
        return []
    prefix = f"missions.m{num}"
    return [(name, mod) for name, mod in sys.modules.items()
            if name == prefix or name.startswith(prefix + ".")]


def capture() -> dict:
    """Serialise the live world into an ``ae.save/1`` snapshot dict."""
    vars_: dict[str, Any] = {}
    # dir(), not vars(): STATE carries class-level defaults that restore()
    # materialises on the instance; both captures must see the same keys.
    for k in dir(STATE):
        if k.startswith("_"):
            continue
        try:
            v = getattr(STATE, k)
        except Exception:
            continue
        if callable(v):
            continue
        cv = _clean(v)
        if cv is not None:
            vars_[k] = cv
    pl = getattr(STATE, "player", None)
    if pl is not None and hasattr(pl, "rect"):
        vars_["__player_rect"] = [int(x) for x in pl.rect]
        for a in ("health", "hp"):
            if hasattr(pl, a):
                vars_["__player_hp"] = getattr(pl, a)
                break
        vars_["__player_legacy"] = _object_attrs(pl)
    from engine.core import LEGACY_RNG
    # STATE lists of live objects (casings, fire zones, particles, story
    # props): capture per-object plain attrs; restore matches by index.
    for k, v in vars(STATE).items():
        if k in ("enemies",) or k.startswith("__"):
            continue
        if isinstance(v, list) and v and hasattr(v[0], "__dict__"):
            items, rebuild = [], True
            for o in v:
                attrs = _object_attrs(o)
                # Rebuild is only sound when every instance attr was
                # captured (a Rect/object attr would be lost; e.g. Door).
                if len(attrs) < len([x for x in vars(o).values() if not callable(x)]):
                    rebuild = False
                items.append({"cls": f"{type(o).__module__}.{type(o).__qualname__}",
                              "attrs": attrs})
            vars_["__objs__" + k] = {"rebuild": rebuild, "items": items}
    mission_key = str(getattr(STATE, "active_mission_id", "") or "")
    vars_["__modules__"] = {
        name: {k: cv for k, v in vars(mod).items()
               if not k.startswith("__") and not callable(v)
               for cv in [_clean(v)] if cv is not None}
        for name, mod in _mission_modules(mission_key)}
    vars_["__scene_stack"] = [str(getattr(STATE, "game_state", ""))]
    frame = int(getattr(STATE, "frame_count", 0) or 0)
    snap = {
        "schema": _save.SCHEMA,
        "id": "live",
        "frame": frame,
        "mission": str(getattr(STATE, "active_mission_id", "") or "") or "none",
        "vars": vars_,
        "world": _world_dump(),
        "rng": {"random": _rng_state_json(random),
                "legacy": _rng_state_json(LEGACY_RNG)},
        "clock": {"frame": frame},
    }
    return _save.from_dict(snap)


def restore(snap: dict) -> None:
    """Write a snapshot back onto live state (see module docstring)."""
    snap = _save.from_dict(snap)
    for k, v in snap["vars"].items():
        if k.startswith("__"):
            continue
        # Deep copy: the game must never hold the snapshot's own mutables,
        # or a later run would write back into the snapshot (aliasing).
        _set_attr(STATE, k, _unclean(v))
    vars_ = snap["vars"]
    pl = getattr(STATE, "player", None)
    if pl is not None and "__player_rect" in vars_:
        try:
            pl.rect.topleft = (vars_["__player_rect"][0], vars_["__player_rect"][1])
        except Exception:
            pass
        if "__player_hp" in vars_:
            for a in ("health", "hp"):
                if hasattr(pl, a):
                    setattr(pl, a, vars_["__player_hp"])
                    break
        for f, val in vars_.get("__player_legacy", {}).items():
            try:
                _set_attr(pl, f, _unclean(val))
            except Exception:
                pass
    if "frame_count" in vars(STATE):
        STATE.frame_count = snap["frame"]
    import sys
    for name, fields in snap["vars"].get("__modules__", {}).items():
        mod = sys.modules.get(name)
        if mod is None:
            continue
        for f, val in fields.items():
            try:
                restored = _unclean(val)
                existing = getattr(mod, f, None)
                if isinstance(existing, dict) and isinstance(restored, dict):
                    existing.update(restored)   # uncapturable entries survive
                else:
                    setattr(mod, f, restored)
            except Exception:
                pass
    for k, objs in snap["vars"].items():
        if not k.startswith("__objs__"):
            continue
        live_list = getattr(STATE, k[len("__objs__"):], None)
        if not isinstance(live_list, list):
            continue
        if not objs.get("rebuild"):
            for obj, entry in zip(live_list, objs["items"]):
                for f, val in entry["attrs"].items():
                    try:
                        _set_attr(obj, f, _unclean(val))
                    except Exception:
                        pass
            del live_list[len(objs["items"]):]
            continue
        # Rebuild wholesale: these lists (casings, fire zones, particles,
        # props) churn identity as objects spawn/die, so index-matching is
        # unsound; only the list itself references them.
        rebuilt = []
        for entry in objs["items"]:
            try:
                mod_name, _, qual = entry["cls"].rpartition(".")
                cls = sys.modules[mod_name]
                for part in qual.split("."):
                    cls = getattr(cls, part)
                obj = cls.__new__(cls)
                for f, val in entry["attrs"].items():
                    try:
                        _set_attr(obj, f, _unclean(val))
                    except Exception:
                        pass
                rebuilt.append(obj)
            except Exception:
                pass
        live_list[:] = rebuilt
    try:
        from engine.core import LEGACY_RNG
        _rng_state_restore(random, snap["rng"]["random"])
        _rng_state_restore(LEGACY_RNG, snap["rng"]["legacy"])
    except Exception:
        pass
    live = list(getattr(STATE, "enemies", []) or [])
    try:
        import game.world as gw  # lazy: booted by game_core
        w = gw.world() if gw.installed() else None
    except Exception:
        w = None
    by_eid: dict[int, Any] = {}
    if w is not None:
        roster = gw.roster()
        for e in live:
            eid = roster.eid_for(e)
            if eid is not None:
                by_eid[int(eid)] = e
    entries = snap["world"].get("enemies", [])
    for entry in entries:
        e = by_eid.get(entry.get("eid", -1))
        if e is None and 0 <= entry.get("idx", -1) < len(live):
            e = live[entry["idx"]]
        if e is None:
            continue
        # Components first (dataclass storage), legacy attrs last: legacy
        # objects are the ground truth the views read, and view setters are
        # not always the inverse of the dump (unit-scaling adapters).
        if w is not None and "eid" in entry:
            for name, fields in entry.get("components", {}).items():
                comp = w.get(entry["eid"], w.by_name(name), None)
                if comp is None:
                    continue
                for f, val in fields.items():
                    try:
                        setattr(comp, f, _unclean(val))
                    except Exception:
                        pass
        for f, val in entry.get("legacy", {}).items():
            try:
                _set_attr(e, f, _unclean(val))
            except Exception:
                pass
    # Restore roster order for the survivors, captured order first.
    ordered = []
    for entry in entries:
        e = by_eid.get(entry.get("eid", -1))
        if e is not None and e not in ordered:
            ordered.append(e)
    if ordered and len(ordered) == len(live):
        STATE.enemies = ordered


def statehash(snap: dict | None = None) -> str:
    return _save.statehash(snap if snap is not None else capture())


def capture_m5_checkpoint(name: str) -> None:
    """Snapshot alongside the legacy M5 checkpoint save (never raises)."""
    try:
        from core import save_system
        data = save_system.load_data()
        idx = save_system.current_slot_index()
        slot = data["slots"][idx]
        if slot.get("occupied"):
            snap = capture()
            snap["mission"] = "MISSION5"
            snap["vars"]["__checkpoint"] = name
            slot["snapshot"] = snap
            save_system.save_data(data)
    except Exception:
        pass
