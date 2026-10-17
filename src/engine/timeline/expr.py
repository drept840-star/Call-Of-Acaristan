"""timeline.expr - the tiny safe expression evaluator (RPE6 §6.7/§6.15).

Set and timeline values may be expressions bound to parameters, e.g.
``"lerp(-3.2, -2.9, k)"`` or ``"1.3 + i*0.18"``.  This evaluator walks a
whitelisted AST: numbers, parameter names, ``+ - * / // % **``, unary
sign, comparisons, and the functions ``lerp``, ``clamp``, ``min``, ``max``,
``abs``, ``smoothstep``, ``ease_in``, ``ease_out``, ``ease_in_out``.
Anything else raises :class:`ExprError`.  ``eval`` is never used.
"""
from __future__ import annotations

import ast
import math

__all__ = ["ExprError", "evaluate", "check"]


class ExprError(ValueError):
    """An expression is malformed or uses a construct outside the whitelist."""


def _lerp(a, b, t):
    return a + (b - a) * t


def _clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def _smoothstep(t):
    t = _clamp(float(t))
    return t * t * (3.0 - 2.0 * t)


_FUNCS = {
    "lerp": _lerp,
    "clamp": _clamp,
    "min": min,
    "max": max,
    "abs": abs,
    "smoothstep": _smoothstep,
    "ease_in": lambda t: float(t) * float(t),
    "ease_out": lambda t: 1.0 - (1.0 - float(t)) ** 2,
    "ease_in_out": lambda t: _smoothstep(t),
    "sin": math.sin,
    "cos": math.cos,
}

_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
}


def _eval(node: ast.AST, params: dict) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body, params)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ExprError(f"constant {node.value!r} is not a number")
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id in params:
            v = params[node.id]
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ExprError(f"parameter {node.id!r} is not a number")
            return float(v)
        raise ExprError(f"unknown parameter {node.id!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return float(_BINOPS[type(node.op)](_eval(node.left, params), _eval(node.right, params)))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _eval(node.operand, params)
        return v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise ExprError("only whitelisted functions may be called")
        if node.keywords:
            raise ExprError("keyword arguments are not allowed in expressions")
        return float(_FUNCS[node.func.id](*[_eval(a, params) for a in node.args]))
    raise ExprError(f"construct {type(node).__name__} is not allowed in expressions")


def evaluate(expr, params: dict | None = None) -> float:
    """Evaluate ``expr`` (a number passes through) against ``params``."""
    if isinstance(expr, (int, float)) and not isinstance(expr, bool):
        return float(expr)
    if not isinstance(expr, str):
        raise ExprError(f"expression must be a string or number, got {type(expr).__name__}")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ExprError(f"invalid expression {expr!r}: {e}") from e
    return _eval(tree, dict(params or {}))


def check(expr, params: dict | None = None) -> str | None:
    """None if ``expr`` evaluates against ``params``, else the problem text."""
    try:
        evaluate(expr, params)
    except ExprError as e:
        return str(e)
    except Exception as e:  # noqa: BLE001 - a validator must not crash
        return f"{type(e).__name__}: {e}"
    return None
