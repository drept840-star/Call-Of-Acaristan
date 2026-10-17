#!/usr/bin/env python3
"""ae_d4_replay_compat.py - proof that moving entity data into components kept behaviour (RPE6 Phase 5).

    python tools/ae_d4_replay_compat.py [--set baseline_v0] [--only m5]

Replays a *version-1* baseline (which hashed the ad hoc ``e.m5_*`` instance attributes)
against the current code, re-injecting each component field that the mission code
assigned - under its old attribute name, only on the enemies it was assigned on - right
before every snapshot and removing it right after. If all per-second hashes match, the
component move changed representation only, not behaviour. Evidence tool; delete after Phase 5.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ae_replay as R  # noqa: E402  (boots the headless game, pins clocks)

import game.world as _gw  # noqa: E402
from engine.world import Label  # noqa: E402
from missions.m2.components import M2Role  # noqa: E402
from missions.m3.components import M3Door, M3Guard  # noqa: E402
from missions.m4.components import M4Guard  # noqa: E402
from missions.m5.components import M5Guard  # noqa: E402

# segment -> component kind -> {field: legacy attribute}
LEGACY_BY_SEG = {
    "m2": {M2Role: {"ipa": "is_mission2_ipa", "sniper": "is_mission2_sniper"}},
    "m3": {M3Guard: {"ipa": "is_mission3_ipa", "always_alert": "m3_always_alert", "damage": "m3_damage",
                     "fire_cooldown": "m3_fire_cooldown", "spread": "m3_spread", "bullet_speed": "m3_bullet_speed",
                     "attack_range": "m3_attack_range", "target_kind": "m3_target_kind", "target_timer": "m3_target_timer",
                     "called_alert": "m3_called_alert", "sweep_team": "m3_sweep_team", "sweep_role": "m3_sweep_role",
                     "shield_angle_width": "shield_angle_width"},
           Label: {"kind": "m3_type", "text": "m3_label"},
           M3Door: {"cell_door": "m3_cell_door", "forced_open": "m3_forced_open", "shot_hits": "m3_shot_hits",
                    "required_shots": "m3_required_shots", "archive_access": "m3_archive_access", "ko_breach": "m3_ko_breach",
                    "ko_beat_gate": "m3_ko_beat_gate", "bcast_gate": "m3_bcast_gate", "vostral_vault": "m3_vostral_vault",
                    "kill_order_exit": "m3_kill_order_exit"}},
    "m4": {M4Guard: {"loyalist": "m4_loyalist"}, Label: {"kind": "m4_type", "text": "m4_label"}},
    "m5": {M5Guard: {"guard": "m5_guard", "kind": "m5_type", "label": "m5_label", "stage": "m5_stage",
                     "counted": "m5_counted", "squad": "m5_squad", "face": "m5_face", "passive": "m5_passive",
                     "hunt_prev": "m5_hunt_prev", "hp0": "m5_hp0"}},
}
LEGACY: dict = {}   # active map (set per segment)
_touched: dict[int, set] = {}


_constructing: set[int] = set()


def _track(kind):
    """Record which fields mission code assigns after construction (defaults do not count)."""
    orig_set, orig_init = kind.__setattr__, kind.__init__

    def __init__(self, *a, **k):
        _constructing.add(id(self))
        try:
            orig_init(self, *a, **k)
        finally:
            _constructing.discard(id(self))

    def __setattr__(self, name, value):
        if id(self) not in _constructing:
            _touched.setdefault(id(self), set()).add(name)
        orig_set(self, name, value)
    kind.__init__, kind.__setattr__ = __init__, __setattr__


def _snapshot_compat():
    injected = []
    objs = list(_gw.roster()._obj_of.values()) if _gw.installed() else []   # enemies, doors, ... (registered objects)
    for e in objs:
        for kind, names in LEGACY.items():
            comp = _gw.get(e, kind)
            if comp is None:
                continue
            for field in _touched.get(id(comp), ()):
                if field in names:
                    object.__setattr__(e, names[field], getattr(comp, field))
                    injected.append((e, names[field]))
    snap = _orig_snapshot()
    for e, attr in injected:
        delattr(e, attr)
    snap["_fields"].pop("~world", None)   # version-1 hash: STATE fields only
    snap["hash"] = R.hashlib.sha256("\n".join(f"{k}={v}" for k, v in snap["_fields"].items()).encode()).hexdigest()[:16]
    return snap


_orig_snapshot = R.snapshot
R.snapshot = _snapshot_compat
for _k in {k for seg in LEGACY_BY_SEG.values() for k in seg}:
    _track(_k)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="baseline_v0")
    ap.add_argument("--only", default="", help="segments; baselines are sequential (B-013), so run them all")
    a = ap.parse_args()
    d = R.ROOT / "tests" / "replay" / a.set
    ok = True
    for seg in [s for s in R.SEGMENTS if not a.only or s in a.only.split(",")]:
        _touched.clear()
        LEGACY.clear()
        LEGACY.update(LEGACY_BY_SEG.get(seg, {}))
        base = json.loads((d / f"{seg}.json").read_text(encoding="utf-8"))
        res = R.run_segment(seg, base["input_stream"])
        bad = [(b["t_s"], b["hash"], r["hash"]) for b, r in zip(base["snapshots"], res["snapshots"]) if b["hash"] != r["hash"]]
        n = len(base["snapshots"])
        if bad or n != len(res["snapshots"]):
            ok = False
            print(f"{seg}: FAIL {len(bad)} of {n} snapshots differ (first t={bad[0][0]}s {bad[0][1]} != {bad[0][2]})" if bad
                  else f"{seg}: FAIL snapshot count {n} != {len(res['snapshots'])}")
        else:
            print(f"{seg}: OK {n}/{n} version-1 hashes reproduced with legacy-name injection "
                  f"(final {res['snapshots'][-1]['hash']}, components tracked: {len(_touched)})")
    print("AE D4 REPLAY COMPAT:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
