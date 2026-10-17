"""dialogue.model - the .dlg.json model and static validation (RPE6 §6.14).

``validate(data, text_table=None)`` returns human-readable problems: schema/id
shape, unknown keys, dangling ``next``/choice targets, unreachable nodes,
unknown speakers, missing string keys (when a text table is given), and lines
that exceed ``max_chars`` (a cheap proxy for the box-fit check; the precise
font-metrics fit runs in the game-side checker where fonts exist).
"""
from __future__ import annotations

import json
from typing import Any, Mapping

__all__ = ["SCHEMA", "DialogueError", "Dialogue", "validate", "from_dict", "loads_dialogue", "load_dialogue"]

SCHEMA = "ae.dialogue/1"
_TOP = {"schema", "id", "start", "speakers", "nodes", "metadata"}
_NODE_KEYS = {"speaker", "text", "text_key", "next", "choices", "condition", "effects", "timing"}


class DialogueError(ValueError):
    """A dialogue file is missing, malformed, or fails validation."""


class Dialogue:
    __slots__ = ("id", "start", "speakers", "nodes", "metadata", "source")

    def __init__(self, data: dict, source: str = "") -> None:
        self.id = data["id"]
        self.nodes = data["nodes"]
        self.start = data.get("start") or next(iter(self.nodes))
        self.speakers = dict(data.get("speakers", {}))
        self.metadata = dict(data.get("metadata", {}))
        self.source = source

    def node(self, node_id: str) -> dict:
        return self.nodes[node_id]

    def __contains__(self, node_id: str) -> bool:
        return node_id in self.nodes

    def __len__(self) -> int:
        return len(self.nodes)


def _targets(node: dict):
    nxt = node.get("next")
    if nxt:
        yield nxt
    for c in node.get("choices", []) or []:
        if isinstance(c, dict) and c.get("next"):
            yield c["next"]


def validate(data: Any, text_table: Mapping[str, str] | None = None, max_chars: int = 220) -> list[str]:
    out: list[str] = []
    if not isinstance(data, dict):
        return ["dialogue is not a JSON object"]
    for k in data:
        if k not in _TOP:
            out.append(f"unknown top-level key {k!r}")
    if data.get("schema") != SCHEMA:
        out.append(f"schema is {data.get('schema')!r}, expected {SCHEMA!r}")
    if not isinstance(data.get("id"), str) or not data["id"]:
        out.append("id missing")
    nodes = data.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        out.append("nodes missing or empty")
        return out
    speakers = data.get("speakers", {})
    if not isinstance(speakers, dict):
        out.append("speakers is not an object")
        speakers = {}
    start = data.get("start") or next(iter(nodes))
    if start not in nodes:
        out.append(f"start node {start!r} not in nodes")
    for nid, node in nodes.items():
        if not isinstance(node, dict):
            out.append(f"node {nid!r}: not an object")
            continue
        for k in node:
            if k not in _NODE_KEYS:
                out.append(f"node {nid!r}: unknown key {k!r}")
        sp = node.get("speaker")
        if sp is not None and speakers and sp not in speakers:
            out.append(f"node {nid!r}: unknown speaker {sp!r}")
        text = node.get("text")
        tkey = node.get("text_key")
        if text is None and tkey is None:
            out.append(f"node {nid!r}: neither text nor text_key")
        if isinstance(text, str) and len(text) > max_chars:
            out.append(f"node {nid!r}: text {len(text)} chars > {max_chars} (box fit)")
        if tkey is not None and text_table is not None:
            if tkey not in text_table:
                out.append(f"node {nid!r}: text_key {tkey!r} missing from the string table")
            elif len(text_table[tkey]) > max_chars:
                out.append(f"node {nid!r}: resolved text {len(text_table[tkey])} chars > {max_chars} (box fit)")
        for tgt in _targets(node):
            if tgt not in nodes:
                out.append(f"node {nid!r}: target {tgt!r} not in nodes")
        for c in node.get("choices", []) or []:
            if not isinstance(c, dict) or ("label" not in c and "label_key" not in c):
                out.append(f"node {nid!r}: choice without label/label_key")
    # reachability from start (following next + choices, ignoring conditions)
    seen, stack = set(), [start] if start in nodes else []
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in nodes:
            continue
        seen.add(cur)
        stack.extend(_targets(nodes[cur]))
    for nid in nodes:
        if nid not in seen:
            out.append(f"node {nid!r}: unreachable from start {start!r}")
    return out


def from_dict(data: dict, source: str = "") -> Dialogue:
    problems = validate(data)
    if problems:
        raise DialogueError(f"{source or 'dialogue'}: " + "; ".join(problems))
    return Dialogue(data, source)


def loads_dialogue(text: str, source: str = "<string>") -> Dialogue:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise DialogueError(f"{source}: invalid JSON: {e}") from e
    return from_dict(data, source)


def load_dialogue(path: str) -> Dialogue:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        raise DialogueError(f"cannot read dialogue {path}: {e}") from e
    return loads_dialogue(text, path)
