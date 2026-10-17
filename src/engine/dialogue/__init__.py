"""engine.dialogue - data-driven dialogue (RPE6 §6.14, Phase 7).

A ``.dlg.json`` file holds a graph of nodes::

    {"schema": "ae.dialogue/1", "id": "m5.maru_beats", "start": "b0",
     "speakers": {"MARU": {"color": [198, 168, 120]}},
     "nodes": {"b0": {"speaker": "MARU", "text_key": "m5.beat.0", "next": "b1"},
               "b1": {"speaker": "BIRIBEL", "text": "...", "choices": [...]}}}

Node fields: ``speaker``, ``text`` (literal) or ``text_key`` (string-table key),
``next`` (node id or null), ``choices`` (``[{label/label_key, next, condition}]``),
``condition`` (a *data string* - ``flag("x")``, ``var("heat") > 2`` - evaluated by
the host's condition evaluator, never by ``eval`` here), ``effects``
(``[{set: name, value}, {emit: name}, {objective: key}]``), ``timing``
(``{auto_ms, hold_until_input}``).

``DialogueRunner`` walks the graph against a ``DialogueHost`` (the game side:
flags/vars, event sink, text resolution) and yields ``DialogueLine`` events; it
never imports game code and never draws - ``ui.DialogueBox`` rendering stays with
the caller. ``validate`` is the static checker the CI tool runs.
"""
from __future__ import annotations

from .model import SCHEMA, Dialogue, DialogueError, from_dict, load_dialogue, loads_dialogue, validate
from .runner import DialogueEnded, DialogueHost, DialogueLine, DialogueRunner

__all__ = ["SCHEMA", "Dialogue", "DialogueError", "DialogueEnded", "DialogueHost", "DialogueLine", "DialogueRunner",
           "from_dict", "load_dialogue", "loads_dialogue", "validate"]
