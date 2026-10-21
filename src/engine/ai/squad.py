"""engine.ai.squad - what a group of agents shares.

``report``/``intel``  a sighting reaches the rest of the squad ``radio`` seconds
                      later (an instant report skips the delay: an officer).
``fire_token``        at most ``shooters`` agents fire at once; the others hold.
                      This is what keeps a room of enemies from shredding the
                      player in the same half second, and it makes them take
                      turns, which reads as coordination.
``claim``             reserve a place (a cover spot) so two agents don't pick it.
"""
from __future__ import annotations

from typing import Any, Hashable, Sequence

__all__ = ["Squad"]


class Squad:
    def __init__(self, shooters: int = 2, radio: float = 1.0) -> None:
        self.shooters = int(shooters)
        self.radio = float(radio)
        self._pending: list[tuple[float, tuple[float, ...], Any]] = []   # (arrives, pos, by)
        self._heard: dict[Any, tuple[float, tuple[float, ...], Any]] = {}  # latest per reporter
        self._tokens: dict[Any, float] = {}
        self._claims: dict[Hashable, Any] = {}

    # ── contact reports ───────────────────────────────────────────────
    def report(self, t: float, pos: Sequence[float], by: Any = None, instant: bool = False) -> None:
        at = t if instant else t + self.radio
        pend = self._pending
        if pend and not instant and at - pend[-1][0] < 0.1:
            pend[-1] = (pend[-1][0], tuple(pos), by)     # same transmission
        else:
            pend.append((at, tuple(pos), by))
            pend.sort(key=lambda r: r[0])

    def intel(self, t: float, me: Any = None) -> tuple[tuple[float, ...], float] | None:
        """(pos, time it arrived) of the latest report that has reached ``t``,
        not counting the agent's own."""
        pend = self._pending
        while pend and pend[0][0] <= t:
            r = pend.pop(0)
            self._heard[r[2]] = r
        best = None
        for by, (at, pos, _by) in self._heard.items():
            if (me is None or by != me) and (best is None or at > best[1]):
                best = (pos, at)
        return best

    # ── fire tokens ───────────────────────────────────────────────────
    def fire_token(self, t: float, who: Any, hold: float) -> bool:
        """Take (or keep) a token for ``hold`` seconds; False when the squad's
        shooters are all busy."""
        for k in [k for k, until in self._tokens.items() if until <= t]:
            del self._tokens[k]
        if who in self._tokens or len(self._tokens) < self.shooters:
            self._tokens[who] = max(self._tokens.get(who, t), t + hold)
            return True
        return False

    def has_token(self, t: float, who: Any) -> bool:
        return self._tokens.get(who, -1.0) > t

    def release(self, who: Any) -> None:
        self._tokens.pop(who, None)

    # ── claims ────────────────────────────────────────────────────────
    def claim(self, key: Hashable, who: Any) -> bool:
        owner = self._claims.get(key)
        if owner is not None and owner != who:
            return False
        for k in [k for k, o in self._claims.items() if o == who and k != key]:
            del self._claims[k]
        self._claims[key] = who
        return True

    def claimed(self, key: Hashable, by_other_than: Any = None) -> bool:
        owner = self._claims.get(key)
        return owner is not None and owner != by_other_than

    def claims(self) -> dict[Hashable, Any]:
        return dict(self._claims)

    def unclaim(self, who: Any) -> None:
        for k in [k for k, o in self._claims.items() if o == who]:
            del self._claims[k]

    def forget(self, who: Any) -> None:
        """An agent is gone: free its token and claims."""
        self.release(who)
        self.unclaim(who)
