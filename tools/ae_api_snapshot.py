#!/usr/bin/env python3
"""ae_api_snapshot.py - public API snapshot of ``src/engine`` (RPE6 Phase 2 gate).

    python tools/ae_api_snapshot.py record     # write tests/api/engine_api.json
    python tools/ae_api_snapshot.py check      # compare the live engine against it
    python tools/ae_api_snapshot.py check --verbose

What is captured, per ``engine`` package/module (walked from src/engine, imported
headless):
  * the module's ``__all__`` (missing ``__all__`` is an error: rule R5 asks for
    explicit facades),
  * for every exported name: its kind (class / function / constant / module),
    the signature of functions, and for classes the public methods with their
    signatures, public class attributes and the public ``__slots__``/dataclass fields.

``check`` fails on *any* difference - additions included - so a change to the
engine's public surface is always a deliberate ``record`` (reviewed in the diff
of tests/api/engine_api.json), never a side effect. Private names (leading
underscore) are ignored everywhere. Importing the engine must stay side-effect
free, so the snapshot never opens a window or touches audio.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import pathlib
import json
import os
import pkgutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SNAP = ROOT / "tests" / "api" / "engine_api.json"
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))



def _type_name(obj) -> str:
    """Platform-neutral type name: concrete pathlib classes (WindowsPath/PosixPath) record as 'Path'."""
    if isinstance(obj, pathlib.PurePath):
        return "Path"
    return type(obj).__name__

def _sig(obj) -> str:
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return "(...)"


def _describe(name: str, obj) -> dict:
    if inspect.ismodule(obj):
        # a namespace exported by a facade (e.g. engine.assets.artpack): snapshot its own public surface
        inner = {n: _describe(n, getattr(obj, n)) for n in getattr(obj, "__all__", ()) if hasattr(obj, n)}
        return {"kind": "module", "module": obj.__name__, "all": list(getattr(obj, "__all__", ())), "names": inner}
    if inspect.isclass(obj):
        methods, attrs = {}, {}
        for attr, val in sorted(vars(obj).items()):
            if attr.startswith("_") and attr not in ("__init__", "__call__", "__enter__", "__exit__",
                                                      "__iter__", "__len__", "__contains__", "__getitem__"):
                continue
            if isinstance(val, (staticmethod, classmethod)):
                methods[attr] = ("static " if isinstance(val, staticmethod) else "class ") + _sig(val.__func__)
            elif inspect.isfunction(val):
                methods[attr] = _sig(val)
            elif isinstance(val, property):
                methods[attr] = "property"
            elif not callable(val):
                attrs[attr] = _type_name(val)
        out = {"kind": "class", "bases": [b.__name__ for b in obj.__bases__ if b is not object],
               "methods": methods, "attrs": attrs}
        fields = getattr(obj, "__dataclass_fields__", None)
        if fields:
            out["fields"] = sorted(f for f in fields if not f.startswith("_"))
        return out
    if inspect.isroutine(obj):
        return {"kind": "function", "signature": _sig(obj)}
    return {"kind": "constant", "type": _type_name(obj)}


def snapshot() -> tuple[dict, list[str]]:
    import engine
    errors: list[str] = []
    out: dict = {"engine_version": getattr(engine, "__version__", "?"), "modules": {}}
    names = ["engine"] + sorted(m.name for m in pkgutil.walk_packages(engine.__path__, "engine."))
    for modname in names:
        if any(p.startswith("_") for p in modname.split(".")[1:]):
            continue
        try:
            mod = importlib.import_module(modname)
        except Exception as e:   # noqa: BLE001 - reported, not masked
            errors.append(f"{modname}: import failed: {e!r}")
            continue
        exported = getattr(mod, "__all__", None)
        if exported is None:
            errors.append(f"{modname}: no __all__ (R5: explicit public surface)")
            continue
        entry = {}
        for name in exported:
            if name.startswith("_") and not (name.startswith("__") and name.endswith("__")):
                errors.append(f"{modname}: private name {name!r} in __all__")
                continue
            if not hasattr(mod, name):
                errors.append(f"{modname}: __all__ lists {name!r} but the module has no such attribute")
                continue
            entry[name] = _describe(name, getattr(mod, name))
        out["modules"][modname] = {"all": list(exported), "names": entry}
    return out, errors


def _flatten(snap: dict, prefix="") -> dict[str, str]:
    """module.name[.detail] -> value, for line-oriented diffs."""
    flat = {}
    for modname, m in snap["modules"].items():
        flat[f"{modname}.__all__"] = json.dumps(m["all"], sort_keys=True)
        for name, d in m["names"].items():
            base = f"{modname}.{name}"
            for k, v in d.items():
                if isinstance(v, dict):
                    for kk, vv in v.items():
                        flat[f"{base}.{k}.{kk}"] = json.dumps(vv, sort_keys=True)
                else:
                    flat[f"{base}.{k}"] = json.dumps(v, sort_keys=True)
    return flat


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["record", "check"])
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    snap, errors = snapshot()
    nmod, nnames = len(snap["modules"]), sum(len(m["names"]) for m in snap["modules"].values())
    for e in errors:
        print(f"  ERROR {e}")
    if a.cmd == "record":
        if errors:
            print(f"AE API: FAIL (not recorded: {len(errors)} errors)")
            return 1
        SNAP.parent.mkdir(parents=True, exist_ok=True)
        SNAP.write_text(json.dumps(snap, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"AE API: recorded {nmod} modules, {nnames} public names -> {SNAP.relative_to(ROOT)}")
        return 0
    if not SNAP.exists():
        print(f"AE API: FAIL (no snapshot at {SNAP.relative_to(ROOT)}; run 'record')")
        return 1
    base = json.loads(SNAP.read_text(encoding="utf-8"))
    bf, nf = _flatten(base), _flatten(snap)
    added = sorted(k for k in nf if k not in bf)
    removed = sorted(k for k in bf if k not in nf)
    changed = sorted(k for k in nf if k in bf and nf[k] != bf[k])
    for k in removed:
        print(f"  - {k} = {bf[k]}")
    for k in added:
        print(f"  + {k} = {nf[k]}")
    for k in changed:
        print(f"  ~ {k}: {bf[k]} -> {nf[k]}")
    if a.verbose:
        for modname, m in snap["modules"].items():
            print(f"  {modname}: {', '.join(m['all']) or '-'}")
    bad = bool(errors or added or removed or changed)
    print(f"AE API: {'FAIL' if bad else 'OK'} ({nmod} modules, {nnames} public names; "
          f"+{len(added)} -{len(removed)} ~{len(changed)}, {len(errors)} errors)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
