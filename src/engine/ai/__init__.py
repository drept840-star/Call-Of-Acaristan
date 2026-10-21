"""engine.ai - enemy brains: behaviour trees, senses, squads and cover.

``bt``     the behaviour tree runtime (one shared tree, per-agent memory)
``senses`` sight with a reaction delay, a noise bus, contact memory
``squad``  shared contact reports with a radio delay, fire tokens, claims
``cover``  cover spots around a ``BoxWorld`` and the scoring that picks one

The world is reached only through what a mission hands in (a ``BoxWorld``, a
``GridNav``, plain callables), so the same brains run any level. Pure Python,
no side effects on import.
"""
from . import bt, cover, senses, squad

__all__ = ["bt", "cover", "senses", "squad"]
