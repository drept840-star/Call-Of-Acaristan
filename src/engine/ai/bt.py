"""engine.ai.bt - a small behaviour tree runtime.

A tree is built once and shared by every agent that runs it: nodes keep no
per-agent state on themselves, only in the agent's blackboard (``ctx.bb``).
Every tick walks from the root:

``Selector``  priority choice: the first child that does not fail wins, and it
              is re-checked from the top every tick, so a higher branch (a
              hit, a sighting) takes over a running lower one, which is halted.
``Sequence``  children in order; resumes at the child that was running.
``Action``    ``fn(ctx)`` returns a status (or a bool); ``ctx.fresh`` is True
              on the first tick of a run; ``halt(ctx)`` runs when preempted.
``Condition`` ``fn(ctx)`` -> bool; ``If(fn, child)`` guards a branch, re-checked
              every tick (a running child is halted when it stops holding).
``Wait``, ``Cooldown``, ``Timeout``, ``Invert``: the usual decorators.

``ctx.trace`` collects the names of the branches that ran this tick, outermost
first ("fight > cover > peek"); a debug overlay can show it.
"""
from __future__ import annotations

import itertools
from typing import Any, Callable

__all__ = ["SUCCESS", "FAILURE", "RUNNING", "Ctx", "Node", "Selector", "Sequence",
           "Action", "Condition", "If", "Wait", "Cooldown", "Timeout", "Invert", "Tree"]

SUCCESS = "success"
FAILURE = "failure"
RUNNING = "running"

_ids = itertools.count(1)


class Ctx:
    """One agent's tick. ``world`` is whatever the mission hands in."""

    __slots__ = ("agent", "bb", "t", "dt", "world", "trace", "fresh")

    def __init__(self, agent: Any, bb: dict, t: float, dt: float, world: Any = None) -> None:
        self.agent = agent
        self.bb = bb
        self.t = float(t)
        self.dt = float(dt)
        self.world = world
        self.trace: list[str] = []
        self.fresh = False


def _status(v: Any) -> str:
    if v is True:
        return SUCCESS
    if v is False or v is None:
        return FAILURE
    return v


class Node:
    def __init__(self, name: str = "") -> None:
        self.name = name
        self.key = next(_ids)

    def mem(self, ctx: Ctx) -> dict:
        return ctx.bb.setdefault("_bt", {}).setdefault(self.key, {})

    def run(self, ctx: Ctx) -> str:
        mark = len(ctx.trace)
        if self.name:
            ctx.trace.append(self.name)
        status = self.tick(ctx)
        if status == FAILURE:
            del ctx.trace[mark:]
        return status

    def tick(self, ctx: Ctx) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def halt(self, ctx: Ctx) -> None:
        """Preempted while running: drop per-agent state."""
        ctx.bb.get("_bt", {}).pop(self.key, None)


class Selector(Node):
    def __init__(self, *children: Node, name: str = "") -> None:
        super().__init__(name)
        self.children = children

    def tick(self, ctx: Ctx) -> str:
        m = self.mem(ctx)
        was = m.get("running", -1)
        for i, child in enumerate(self.children):
            status = child.run(ctx)
            if status == FAILURE:
                continue
            if was != -1 and was != i:
                self.children[was].halt(ctx)
            m["running"] = i if status == RUNNING else -1
            return status
        if was != -1:
            self.children[was].halt(ctx)
        m["running"] = -1
        return FAILURE

    def halt(self, ctx: Ctx) -> None:
        was = self.mem(ctx).get("running", -1)
        if was != -1:
            self.children[was].halt(ctx)
        super().halt(ctx)


class Sequence(Node):
    def __init__(self, *children: Node, name: str = "") -> None:
        super().__init__(name)
        self.children = children

    def tick(self, ctx: Ctx) -> str:
        m = self.mem(ctx)
        i = m.get("at", 0)
        while i < len(self.children):
            status = self.children[i].run(ctx)
            if status == RUNNING:
                m["at"] = i
                return RUNNING
            if status == FAILURE:
                m["at"] = 0
                return FAILURE
            i += 1
        m["at"] = 0
        return SUCCESS

    def halt(self, ctx: Ctx) -> None:
        at = self.mem(ctx).get("at", 0)
        if at < len(self.children):
            self.children[at].halt(ctx)
        super().halt(ctx)


class Action(Node):
    def __init__(self, fn: Callable[[Ctx], Any], halt: Callable[[Ctx], None] | None = None,
                 name: str = "") -> None:
        super().__init__(name or getattr(fn, "__name__", "").strip("_"))
        self.fn = fn
        self.on_halt = halt

    def tick(self, ctx: Ctx) -> str:
        m = self.mem(ctx)
        ctx.fresh = not m.get("running", False)
        status = _status(self.fn(ctx))
        ctx.fresh = False
        m["running"] = status == RUNNING
        return status

    def halt(self, ctx: Ctx) -> None:
        if self.mem(ctx).get("running") and self.on_halt is not None:
            self.on_halt(ctx)
        super().halt(ctx)


class Condition(Node):
    def __init__(self, fn: Callable[[Ctx], Any], name: str = "") -> None:
        super().__init__(name)
        self.fn = fn

    def tick(self, ctx: Ctx) -> str:
        return SUCCESS if self.fn(ctx) else FAILURE


class Wait(Node):
    """RUNNING for ``secs`` (a number or ``fn(ctx)``), then SUCCESS."""

    def __init__(self, secs: float | Callable[[Ctx], float], name: str = "") -> None:
        super().__init__(name)
        self.secs = secs

    def tick(self, ctx: Ctx) -> str:
        m = self.mem(ctx)
        if "until" not in m:
            secs = self.secs(ctx) if callable(self.secs) else self.secs
            m["until"] = ctx.t + float(secs)
        if ctx.t >= m["until"]:
            m.pop("until")
            return SUCCESS
        return RUNNING


class _Decorator(Node):
    def __init__(self, child: Node, name: str = "") -> None:
        super().__init__(name)
        self.child = child

    def halt(self, ctx: Ctx) -> None:
        self.child.halt(ctx)
        super().halt(ctx)


class If(_Decorator):
    """Runs the child while ``fn(ctx)`` holds, re-checked every tick; when it
    stops holding a running child is halted and the branch fails."""

    def __init__(self, fn: Callable[[Ctx], Any], child: Node, name: str = "") -> None:
        super().__init__(child, name)
        self.fn = fn

    def tick(self, ctx: Ctx) -> str:
        m = self.mem(ctx)
        if not self.fn(ctx):
            if m.get("running"):
                self.child.halt(ctx)
            m["running"] = False
            return FAILURE
        status = self.child.run(ctx)
        m["running"] = status == RUNNING
        return status


class Invert(_Decorator):
    def tick(self, ctx: Ctx) -> str:
        status = self.child.run(ctx)
        if status == RUNNING:
            return RUNNING
        return FAILURE if status == SUCCESS else SUCCESS


class Cooldown(_Decorator):
    """After the child succeeds it fails for ``secs`` without ticking."""

    def __init__(self, child: Node, secs: float, name: str = "") -> None:
        super().__init__(child, name)
        self.secs = float(secs)

    def tick(self, ctx: Ctx) -> str:
        cd = ctx.bb.setdefault("_cd", {})
        if ctx.t < cd.get(self.key, -1e9):
            return FAILURE
        status = self.child.run(ctx)
        if status == SUCCESS:
            cd[self.key] = ctx.t + self.secs
        return status

    def halt(self, ctx: Ctx) -> None:
        self.child.halt(ctx)        # the cooldown itself survives preemption


class Timeout(_Decorator):
    """Fails (and halts the child) once it has run ``secs`` without finishing."""

    def __init__(self, child: Node, secs: float, name: str = "") -> None:
        super().__init__(child, name)
        self.secs = float(secs)

    def tick(self, ctx: Ctx) -> str:
        m = self.mem(ctx)
        start = m.setdefault("start", ctx.t)
        if ctx.t - start >= self.secs:
            self.halt(ctx)
            return FAILURE
        status = self.child.run(ctx)
        if status != RUNNING:
            m.pop("start", None)
        return status


class Tree:
    def __init__(self, root: Node) -> None:
        self.root = root

    def tick(self, agent: Any, bb: dict, t: float, dt: float, world: Any = None) -> Ctx:
        ctx = Ctx(agent, bb, t, dt, world)
        ctx.bb["_status"] = self.root.run(ctx)
        ctx.bb["_trace"] = " > ".join(ctx.trace)
        return ctx

    def reset(self, bb: dict) -> None:
        bb.pop("_bt", None)
        bb.pop("_cd", None)
