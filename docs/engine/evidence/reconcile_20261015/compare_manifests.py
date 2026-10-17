"""Compare golden manifests: sandbox(A) vs partial `--only` recapture(B) vs full re-baseline(C).

A = build/ae_reconcile/old_golden_manifest.json          sandbox-era hashes (merge 2026-10-14)
B = build/ae_reconcile/golden_v0_partial_recap/manifest.json  owner PNGs + partial --only recapture
C = tests/golden/baseline_v0/manifest.json               full-sequence re-baseline (2026-10-15)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_p = Path(__file__).resolve()
ROOT = next(q for q in _p.parents if (q / 'tests' / 'golden').is_dir())
LINES: list[str] = []


def emit(s: str = "") -> None:
    LINES.append(s)
    print(s)


def load(p):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    return {k: v["sha256"] for k, v in d["shots"].items()}


A = load(ROOT / "build" / "ae_reconcile" / "old_golden_manifest.json")
B = load(ROOT / "build" / "ae_reconcile" / "golden_v0_partial_recap" / "manifest.json")
C = load(ROOT / "tests" / "golden" / "baseline_v0" / "manifest.json")


def diff(x, y, label):
    xs, ys = set(x), set(y)
    only_x, only_y = sorted(xs - ys), sorted(ys - xs)
    ch = sorted(k for k in xs & ys if x[k] != y[k])
    print(f"== {label}: only-first={len(only_x)} only-second={len(only_y)} changed={len(ch)}")
    for k in ch:
        print("    ", k)
    if only_x:
        print("     only-first:", only_x[:10])
    if only_y:
        print("     only-second:", only_y[:10])


print("counts:", len(A), len(B), len(C))
diff(A, C, "sandbox(A) vs full re-baseline(C): true drift (full-sequence vs full-sequence)")
diff(B, C, "partial recapture(B) vs full(C): effective change from the partial step")
diff(A, B, "sandbox(A) vs partial(B): shots overwritten by the partial recapture")
