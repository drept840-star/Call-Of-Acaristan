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
from .bt import (SUCCESS, FAILURE, RUNNING, Ctx, Node, Selector, Sequence,
                 Action, Condition, Wait, If, Invert, Cooldown, Timeout, Tree)
from .cover import (HIDE_EYE_LOW, HIDE_EYE_HIGH, SHOOT_EYE, Spot, build_spots,
                    hides, peek_point, can_peek, pick)
from .senses import NoiseBus, Sight, new_memory, give_lead, drop_lead, on_hit
from .squad import Squad

__all__ = ["bt", "cover", "senses", "squad",
           "SUCCESS", "FAILURE", "RUNNING", "Ctx", "Node", "Selector",
           "Sequence", "Action", "Condition", "Wait", "If", "Invert",
           "Cooldown", "Timeout", "Tree",
           "HIDE_EYE_LOW", "HIDE_EYE_HIGH", "SHOOT_EYE", "Spot", "build_spots",
           "hides", "peek_point", "can_peek", "pick",
           "NoiseBus", "Sight", "new_memory", "give_lead", "drop_lead",
           "on_hit", "Squad"]
