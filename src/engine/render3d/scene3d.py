"""render3d.scene3d - declarative 3D sets (RPE6 §6.7, Phase 8).

A ``.set3d.json`` file describes a 3D set as data::

    {"schema": "ae.set3d/1", "id": "m5/vasile_office",
     "fog": {"color": [12, 11, 10], "start": 8.0, "end": 24.0},
     "light": {"direction": [-0.5, 0.7, -0.5], "ambient": 0.42,
               "diffuse": 0.78, "tint": [1.14, 1.0, 0.84]},
     "nodes": [{"type": "box", "size": [10, 3.2, 0.2],
                "center": [0, 1.6, 3.2], "color": [44, 40, 38]},
               {"type": "repeat", "count": 7, "as": "i",
                "node": {"type": "box", "size": [1.6, 0.06, 0.02],
                         "center": [-1.6, "1.3 + i*0.18", 3.08],
                         "color": [110, 96, 70], "emissive": true}}]}

``build`` flattens nodes into an ordered primitive list (expressions
evaluated against params, ``repeat`` expanded, ``prop_ref`` resolved
through a caller-supplied library).  A ``decal`` node keeps its
``fallback`` primitives attached: the renderer tries the decal asset and
emits the fallback when it is unavailable (the legacy §6.7 semantics).
This module is pure data - it never imports a renderer; the game-side
bridge (`game.render3d_bridge`) turns primitives into meshes.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from engine.timeline.expr import check as _expr_check
from engine.timeline.expr import evaluate as _eval

__all__ = ["SCHEMA", "Set3DError", "Scene3D", "validate", "build", "from_dict", "loads_set3d", "load_set3d"]

SCHEMA = "ae.set3d/1"
_NODE_TYPES = {"box", "quad_xz", "quad", "disc_xz", "decal", "sprite3d", "humanoid", "mesh",
               "prop_ref", "light", "repeat",
               "weather", "emitter", "fog_layer", "puddle"}
_NODE_KEYS = {
    "box": {"type", "size", "center", "color", "cols", "seg", "layer", "emissive", "bias", "attach_light", "texture", "tex_scale"},
    "quad_xz": {"type", "rect", "y", "color", "seg", "layer", "emissive", "bias", "texture", "tex_scale"},
    "quad": {"type", "pts", "color", "layer", "double", "emissive", "bias"},
    "disc_xz": {"type", "center_xz", "r", "y", "color", "n", "layer", "bias"},
    "decal": {"type", "asset", "variant", "center", "size", "facing", "bias", "emissive", "fallback"},
    "sprite3d": {"type", "pos", "size", "color", "asset", "params"},
    "humanoid": {"type", "cast", "outfit", "pose", "pos", "yaw", "look_at", "expression", "speaking"},
    "mesh": {"type", "ref", "pos", "yaw", "scale"},
    "prop_ref": {"type", "ref", "at", "yaw", "params"},
    "light": {"type", "direction", "ambient", "diffuse", "tint", "cast_shadows",
              "kind", "pos", "color", "intensity", "range", "cone"},
    "repeat": {"type", "count", "as", "node"},
    "weather": {"type", "kind", "intensity", "seed"},
    "emitter": {"type", "kind", "pos", "color", "rate", "rise", "spread", "seed", "size"},
    "fog_layer": {"type", "rect", "y", "height", "color", "density"},
    "puddle": {"type", "rect", "y", "reflect"},
}
_VEC_FIELDS = {"center", "pos", "at", "direction", "tint", "pts"}


class Set3DError(ValueError):
    """A set file is missing, malformed, or fails validation."""


class Scene3D:
    __slots__ = ("id", "nodes", "fog", "light", "metadata", "source", "data")

    def __init__(self, data: dict, source: str = "") -> None:
        self.data = data
        self.id = data["id"]
        self.nodes = data.get("nodes", [])
        self.fog = data.get("fog")
        self.light = data.get("light")
        self.metadata = dict(data.get("metadata", {}))
        self.source = source


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_value(v, env, where, out) -> None:
    if isinstance(v, str):
        problem = _expr_check(v, env)
        if problem:
            out.append(f"{where}: {problem}")
    elif isinstance(v, (list, tuple)):
        for i, x in enumerate(v):
            _check_value(x, env, f"{where}[{i}]", out)


def _validate_node(node, env, out, where) -> None:
    if not isinstance(node, dict):
        out.append(f"{where}: not an object")
        return
    ntype = node.get("type")
    if ntype not in _NODE_TYPES:
        out.append(f"{where}: unknown node type {ntype!r}")
        return
    for k in node:
        if k not in _NODE_KEYS[ntype]:
            out.append(f"{where}: unknown key {k!r} for {ntype}")
    if ntype == "repeat":
        count = node.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            out.append(f"{where}: repeat count must be a non-negative int")
        sub_env = dict(env)
        sub_env[str(node.get("as", "i"))] = 0.0
        _validate_node(node.get("node"), sub_env, out, where + ".node")
        return
    if ntype == "prop_ref":
        if not isinstance(node.get("ref"), str) or not node["ref"]:
            out.append(f"{where}: prop_ref needs a ref")
    if ntype == "decal":
        if not isinstance(node.get("asset"), str) or not node["asset"]:
            out.append(f"{where}: decal needs an asset id")
        for j, sub in enumerate(node.get("fallback", []) or []):
            _validate_node(sub, env, out, f"{where}.fallback[{j}]")
    if ntype == "humanoid" and not isinstance(node.get("cast"), str):
        out.append(f"{where}: humanoid needs a cast id")
    if ntype == "mesh" and not isinstance(node.get("ref"), str):
        out.append(f"{where}: mesh needs a mesh ref")
    for field, v in node.items():
        if field in ("type", "asset", "cast", "outfit", "pose", "facing", "ref", "as", "kind", "expression", "texture"):
            continue
        if field == "attach_light" and isinstance(v, dict):
            for k2, v2 in v.items():
                if k2 != "kind":
                    _check_value(v2, env, f"{where}.attach_light.{k2}", out)
            continue
        _check_value(v, env, f"{where}.{field}", out)


def validate(data: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(data, dict):
        return ["set is not a JSON object"]
    for k in data:
        if k not in {"schema", "id", "fog", "light", "lighting", "nodes", "params", "metadata"}:
            out.append(f"unknown top-level key {k!r}")
    lighting = data.get("lighting")
    if lighting is not None and not isinstance(lighting, (str, dict)):
        out.append("lighting must be a preset id or an object")
    if isinstance(lighting, dict):
        for k in lighting:
            if k not in {"preset", "key", "fog", "sky"}:
                out.append(f"lighting: unknown key {k!r}")
    if data.get("schema") != SCHEMA:
        out.append(f"schema is {data.get('schema')!r}, expected {SCHEMA!r}")
    if not isinstance(data.get("id"), str) or not data["id"]:
        out.append("id missing")
    params = data.get("params", {})
    if not isinstance(params, dict):
        out.append("params is not an object")
        params = {}
    env = {k: float(v) for k, v in params.items() if _is_num(v)}
    env.setdefault("k", 0.0)
    env.setdefault("t", 0.0)
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        out.append("nodes missing or empty")
        return out
    for i, node in enumerate(nodes):
        _validate_node(node, env, out, f"node {i}")
    return out


def _value(v, env):
    if isinstance(v, str):
        return _eval(v, env)
    if isinstance(v, (list, tuple)):
        return [_value(x, env) for x in v]
    return v


def _translated(prim: dict, at) -> dict:
    if not at:
        return prim
    prim = dict(prim)
    for field in ("center", "pos"):
        if field in prim and isinstance(prim[field], list):
            prim[field] = [prim[field][i] + at[i] for i in range(3)]
    if "rect" in prim and isinstance(prim["rect"], list):  # quad_xz [x0, z0, x1, z1] + y
        r = prim["rect"]
        prim["rect"] = [r[0] + at[0], r[1] + at[2], r[2] + at[0], r[3] + at[2]]
        if "y" in prim and _is_num(prim["y"]):
            prim["y"] = prim["y"] + at[1]
    return prim


def _build_node(node, env, library, out, depth) -> None:
    if depth > 8:
        raise Set3DError("prop_ref nesting too deep")
    ntype = node["type"]
    if ntype == "repeat":
        var = str(node.get("as", "i"))
        template = node["node"]
        for i in range(int(node["count"])):
            sub = dict(env)
            sub[var] = float(i)
            _build_node(template, sub, library, out, depth)
        return
    if ntype == "prop_ref":
        ref = node["ref"]
        sub_nodes = library.get(ref) if library else None
        if sub_nodes is None:
            raise Set3DError(f"prop_ref {ref!r} not in the prop library")
        at = _value(node.get("at", [0, 0, 0]), env)
        sub_env = dict(env)
        for k, v in (node.get("params") or {}).items():
            sub_env[k] = _value(v, env) if isinstance(v, str) else v
        inner: list = []
        for sub in sub_nodes:
            _build_node(sub, sub_env, library, inner, depth + 1)
        out.extend(_translated(p, at) for p in inner)
        return
    if ntype == "light" and node.get("kind") in ("point", "spot"):
        prim = {"kind": node["kind"] + "_light"}
        for field, v in node.items():
            if field in ("type", "kind"):
                continue
            prim[field] = _value(v, env)
        out.append(prim)
        return
    prim = {"kind": ntype}
    attach = None
    for field, v in node.items():
        if field in ("type", "asset", "cast", "outfit", "pose", "facing", "ref", "as", "expression", "texture"):
            prim[field] = v
            continue
        if field == "kind":
            prim["sub"] = v
            continue
        if field == "attach_light":
            attach = v
            continue
        if field == "fallback":
            inner = []
            for sub in v or []:
                _build_node(sub, env, library, inner, depth)
            prim["fallback"] = inner
            continue
        prim[field] = _value(v, env)
    out.append(prim)
    if attach:  # an emissive part carries its own light (§6.7 step 2)
        spec = {k: _value(v, env) for k, v in attach.items() if k != "kind"}
        off = spec.pop("offset", [0, 0, 0])
        c = prim.get("center", [0, 0, 0])
        spec["pos"] = [c[i] + off[i] for i in range(3)]
        if "flicker" in spec:  # P11 step 10: bridge drives bulb + light
            prim["flicker"] = spec["flicker"]
        out.append({"kind": str(attach.get("kind", "point")) + "_light", **spec})


def build(data: Any, params: Mapping | None = None,
          library: Mapping | None = None, presets: Mapping | None = None) -> list[dict]:
    """Flatten a set (dict or Scene3D) into ordered renderer primitives.

    ``lighting`` (Phase 11) resolves against the ``presets`` library
    first; the set's own ``light``/``fog`` blocks then override single
    fields, so legacy sets without ``lighting`` build identically.
    """
    if isinstance(data, Scene3D):
        data = data.data
    problems = validate(data)
    if problems:
        raise Set3DError("invalid set: " + "; ".join(problems))
    env = {k: float(v) for k, v in (data.get("params") or {}).items() if _is_num(v)}
    if params:
        env.update({k: float(v) for k, v in params.items() if _is_num(v)})
    env.setdefault("k", 0.0)
    env.setdefault("t", 0.0)
    prims: list[dict] = []
    for node in data["nodes"]:
        _build_node(node, env, library or {}, prims, 0)
    fog = {}
    light = {}
    if data.get("lighting") is not None:
        from .presets import resolve as _resolve_preset  # lazy: cycle guard
        spec = data["lighting"]
        if isinstance(spec, dict):  # preset id stays literal; leaves may be exprs
            spec = {k: (v if k == "preset" else _value(v, env)) for k, v in spec.items()}
        resolved = _resolve_preset(spec, presets or {})
        fog.update(resolved["fog"])
        light.update(resolved["key"])
    if data.get("fog"):
        fog.update(_value(data["fog"], env))
    if data.get("light"):
        light.update(_value(data["light"], env))
    head = []
    if fog:
        head.append({"kind": "fog", **fog})
    if light:
        head.append({"kind": "light", **light})
    return head + prims


def from_dict(data: dict, source: str = "") -> Scene3D:
    problems = validate(data)
    if problems:
        raise Set3DError(f"{source or 'set'}: " + "; ".join(problems))
    return Scene3D(data, source)


def loads_set3d(text: str, source: str = "<string>") -> Scene3D:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise Set3DError(f"{source}: invalid JSON: {e}") from e
    return from_dict(data, source)


def load_set3d(path: str) -> Scene3D:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        raise Set3DError(f"cannot read set {path}: {e}") from e
    return loads_set3d(text, path)
