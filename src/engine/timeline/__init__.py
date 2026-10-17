"""engine.timeline - data-driven cutscene timelines (RPE6 §6.15, Phase 8).

A ``.timeline.json`` file sequences a cutscene::

    {"schema": "ae.timeline/1", "id": "m2.intro", "ui_composite": true,
     "shots": [{"scene": "route12_black", "speaker": "VASILE", "text": "...",
                "lighting": [3, 4, 7]}],
     "tracks": {"camera": [{"t": 0, "pos": [0, 1.6, 6]}, ...],
                "event": [{"t": 300, "name": "beat_volkov"}]}}

``shots`` name renderer hooks (the game resolves ``scene`` ids); ``tracks``
are keyframed/clip data sampled deterministically by ``TimelinePlayer`` at
any ``t`` (seek/scrub/step).  Values may be expressions over the timeline
params (``"lerp(-3.2, -2.9, k)"``) evaluated by the whitelisted evaluator in
``timeline.expr`` - never ``eval``.  This package loads, validates and
samples data only; it never imports game code and never draws.
"""
from __future__ import annotations

from .expr import ExprError, check as check_expr, evaluate
from .model import SCHEMA, Timeline, TimelineError, from_dict, load_timeline, loads_timeline, validate
from .player import Sample, TimelinePlayer

__all__ = ["SCHEMA", "ExprError", "Sample", "Timeline", "TimelineError", "TimelinePlayer",
           "check_expr", "evaluate", "from_dict", "load_timeline", "loads_timeline", "validate"]
