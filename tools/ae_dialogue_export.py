#!/usr/bin/env python3
"""ae_dialogue_export - write the legacy conversation tables as ae.dialogue/1 data.

RPE6 Phase 7 (P7-M4).  One-way export from the in-code tables
(``missions.m5.flow._M5_MARU_BEATS``, ``missions.m4.flow._M4_LIAISON_BEATS``)
into ``src/game/content/dialogue/*.dlg.json``.  Speakers are named in the
data; colours stay game-side (``game.dialogues.beats`` resolves them).
Choice follow-up lines become target nodes, exactly as the runtime
splices them in after a choice resolves.

    python tools/ae_dialogue_export.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "src", "game", "content", "dialogue")


def _chain(prefix: str, table, speaker_of=None) -> dict:
    """Linear beat table -> node chain; a choice beat closes the chain."""
    nodes: dict = {}
    order: list[str] = []
    for i, beat in enumerate(table):
        nid = f"{prefix}_{i + 1}"
        order.append(nid)
        if beat.get("type") == "choice" or "options" in beat:
            choices = []
            for j, (label, follow) in enumerate(beat["options"]):
                rid = f"{nid}_resp_{j + 1}"
                nodes[rid] = {"speaker": beat["speaker"], "text": follow, "next": None}
                choices.append({"label": label, "next": rid})
            nodes[nid] = {"speaker": beat["speaker"], "text": beat.get("prompt", ""),
                          "choices": choices, "next": None}
        else:
            nodes[nid] = {"speaker": beat["speaker"], "text": beat["text"], "next": None}
    for a, b in zip(order, order[1:]):
        if nodes[a].get("next") is None and "choices" not in nodes[a]:
            nodes[a]["next"] = b
    speakers: dict = {}
    for beat in table:
        speakers.setdefault(beat["speaker"], {})
    return nodes, speakers, order[0]


def build() -> dict:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import ae_replay  # noqa: F401  (full boot, same as the exporter for levels)
    from missions.m4 import flow as m4_flow
    from missions.m5 import flow as m5_flow

    docs = {}
    nodes, speakers, start = _chain("maru", m5_flow._M5_MARU_BEATS)
    docs["m5.maru"] = {"schema": "ae.dialogue/1", "id": "m5.maru", "start": start,
                       "speakers": speakers, "nodes": nodes,
                       "metadata": {"mission": "m5", "kind": "conversation",
                                    "source": "missions/m5/flow.py _M5_MARU_BEATS"}}
    nodes, speakers, start = _chain("liaison", m4_flow._M4_LIAISON_BEATS)
    docs["m4.liaison"] = {"schema": "ae.dialogue/1", "id": "m4.liaison", "start": start,
                          "speakers": speakers, "nodes": nodes,
                          "metadata": {"mission": "m4", "kind": "conversation",
                                       "source": "missions/m4/flow.py _M4_LIAISON_BEATS"}}
    return docs


def main() -> int:
    dry = "--dry-run" in sys.argv
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    docs = build()
    if not dry:
        os.makedirs(OUT_DIR, exist_ok=True)
    for doc_id, doc in sorted(docs.items()):
        path = os.path.join(OUT_DIR, doc_id + ".dlg.json")
        text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
        if dry:
            print(f"  {doc_id}: {len(doc['nodes'])} nodes (dry run)")
        else:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
    print(f"AE DIALOGUE EXPORT: {'checked' if dry else 'wrote'} {len(docs)} dialogues"
          f" -> src/game/content/dialogue/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
