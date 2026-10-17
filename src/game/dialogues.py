"""game.dialogues - mission conversation access (RPE6 Phase 7).

Conversations live as ``ae.dialogue/1`` data under
``src/game/content/dialogue/<id>.dlg.json`` (validated by
``engine.dialogue``).  At runtime the linear node chain is converted back
into the legacy *beat* dicts the mission typewriter code consumes
(``speaker``/``color``/``text``, plus ``type``/``prompt``/``options`` for
missions whose beats are typed).  Speaker colours stay game-side: callers
pass their own speaker -> RGB map, the data names speakers only.

``ACA_DLG_SRC=legacy`` returns the caller's legacy table untouched, the
strangler fallback (generators/tables stay in code until a later phase
deletes them deliberately).
"""
from __future__ import annotations

import os

from engine.dialogue import load_dialogue

__all__ = ["DIALOGUES_DIR", "use_legacy", "dialogue", "beats"]

DIALOGUES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "dialogue")

_cache: dict = {}


def use_legacy() -> bool:
    return os.environ.get("ACA_DLG_SRC", "").strip().lower() == "legacy"


def dialogue(dialogue_id: str):
    """Load (and cache) one ``ae.dialogue/1`` document by id."""
    if dialogue_id not in _cache:
        _cache[dialogue_id] = load_dialogue(os.path.join(DIALOGUES_DIR, f"{dialogue_id}.dlg.json"))
    return _cache[dialogue_id]


def beats(dialogue_id: str, legacy_beats, colors, typed: bool = False):
    """Legacy beat dicts for ``dialogue_id``.

    Data mode walks the node chain from ``start``; a node's ``choices``
    become a choice beat whose options pair each label with the *target
    node's* text (the spoken follow-up, spliced in by the caller at
    resolve time exactly as the legacy tables did).  Returns a fresh list
    every call - callers splice into it.  Legacy mode returns
    ``legacy_beats`` itself, identity preserved.
    """
    if use_legacy():
        return legacy_beats
    dlg = dialogue(dialogue_id)
    out: list[dict] = []
    node_id = dlg.start
    while node_id is not None:
        node = dlg.node(node_id)
        speaker = node.get("speaker", "")
        color = colors[speaker]
        choices = node.get("choices") or []
        if choices:
            options = [(c.get("label", ""), dlg.node(c["next"]).get("text", "")) for c in choices]
            if typed:
                out.append({"type": "choice", "speaker": speaker, "color": color,
                            "prompt": node.get("text", ""), "options": options})
            else:
                out.append({"speaker": speaker, "color": color,
                            "prompt": node.get("text", ""), "options": options})
            break  # choice targets are follow-up lines, not chain links
        beat = {"speaker": speaker, "color": color, "text": node.get("text", "")}
        if typed:
            beat = {"type": "line", **beat}
        out.append(beat)
        node_id = node.get("next")
    return out
