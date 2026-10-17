#!/usr/bin/env python3
"""ae_dump_components.py - component census of a running mission stage (RPE6 §6.4 acceptance).

    python tools/ae_dump_components.py [--seg m5] [--seconds 3] [--entity N] [--json out.json]

Boots the headless replay harness (tools/ae_replay.py: pinned clock, software renderer,
scripted input), runs the chosen checkpoint for --seconds of simulated time through
core.game_core.game_update, then prints:
  * every component type present in game.world with its fields and live count,
  * the scheduler (phase / order / reads / writes),
  * entity counts per legacy kind (Enemy, Player, Pickup, Corpse, FireZone, NPC),
  * one full entity dump (--entity <eid>, default: the first Enemy).
Exit code 0 when the world holds at least one entity with a Transform.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.chdir(ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("ACARISTAN_RENDERER", "software")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import ae_replay as R  # noqa: E402  (boots pygame + core.config like the replay oracle)
import game.world as _gw  # noqa: E402
from engine.world import LegacyRef, Transform, component_types  # noqa: E402


def run(seg: str, seconds: float) -> None:
    starter, _label = R.SEGMENTS[seg]
    frames = int(seconds * R.FPS)
    R._clock["frame"] = 0
    R._engine_clock().set_wall_elapsed(R._elapsed_ms())
    R.random.seed(R.SEED)
    getattr(R.gc, starter)()
    R.random.seed(R.SEED)
    stream = R.make_stream(R.SEED + sum(map(ord, seg)), frames)
    for f, (held, mpos, fire) in enumerate(R.expand(stream)):
        if f >= frames:
            break
        R._clock["frame"] = f
        R._engine_clock().set_wall_elapsed(R._elapsed_ms())
        R._mouse["pos"] = mpos
        R._mouse["buttons"] = (fire, False, False)
        R.STATE.dt = R.DT
        R.gc.game_update(R.Keys(held))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seg", default="m5", choices=sorted(R.SEGMENTS))
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--entity", type=int, default=0, help="entity id to dump in full (default: first Enemy)")
    ap.add_argument("--json", default="", help="also write the census to this path")
    a = ap.parse_args(argv)

    run(a.seg, a.seconds)
    world = _gw.world()
    sched = _gw.scheduler()
    roster = _gw.roster()
    census = world.dump()
    kinds: dict[str, int] = {}
    first_enemy = 0
    for eid, (ref,) in world.query(LegacyRef):
        kinds[ref.kind] = kinds.get(ref.kind, 0) + 1
        if not first_enemy and ref.kind == "Enemy":
            first_enemy = eid
    target = a.entity or first_enemy or (world.entities()[0] if world.entities() else 0)

    print(f"AE DUMP: segment {a.seg} after {a.seconds:g}s sim ({sched.steps} steps) - "
          f"{census['entities']} entities, {len(census['components'])} component types present, "
          f"{len(list(component_types()))} registered")
    print("components (count / version / fields):")
    for name, info in census["components"].items():
        print(f"  {name:12s} {info['count']:4d}  v{info['version']}  {', '.join(info['fields'])}")
    print("legacy kinds:", ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())) or "-",
          f"| roster spawned={roster.spawned} despawned={roster.despawned}")
    print("systems:")
    for s in sched.describe():
        print(f"  {s['phase']:13s} {s['order']:4d}  {s['name']:18s} reads={s['reads']} writes={s['writes']}")
    if target:
        print(f"entity {target}:")
        for cname, fields in world.dump_entity(target).items():
            print(f"  {cname}: {json.dumps(fields, default=repr)}")
    if a.json:
        out = {"schema": "ae.component_dump/1", "segment": a.seg, "seconds": a.seconds, "census": census,
               "legacy_kinds": kinds, "systems": sched.describe(),
               "entity": {"id": target, "components": world.dump_entity(target)} if target else None}
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=repr)
        print("wrote", a.json)
    ok = world.count(Transform) > 0
    print("AE DUMP:", "OK" if ok else "FAIL (no entity with a Transform)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
