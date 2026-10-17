"""RPE6 one-command CI (D10).  python tools/ae_ci.py [--quick] [--skip name,name]

Runs every gate that exists so far and prints the §13 summary table. Gates that
belong to later phases are listed as `TODO (phase N)` and do not fail the run.
Exit code is non-zero if any implemented gate fails. Logs: build/ae_ci/<gate>.log
--quick skips the slow gates (smoke test, golden, replay, main loop).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
LOGS = ROOT / "build" / "ae_ci"

# (row label, key, command, success regex, detail regex, slow)
GATES = [
    ("compileall", "compileall", [PY, "-m", "compileall", "-q", "src", "tools"], None, None, False),
    ("boundary lint (enforce engine)", "boundaries", [PY, "tools/check_boundaries.py"],
     r"BOUNDARIES: OK", r"BOUNDARIES: \w+ \((.*)\)", False),
    ("import side effects (engine)", "imports", [PY, "tools/ae_import_check.py"],
     r"IMPORT CHECK: OK", r"IMPORT CHECK: \w+ \((.*)\)", False),
    ("import hygiene (no star re-exports)", "star", [PY, "tools/ae_narrow_star.py", "--verify"],
     r"AE NARROW: OK", r"AE NARROW: \w+ \((.*)\)", False),
    ("global names (no unresolved globals)", "globals", [PY, "tools/ae_global_names.py"],
     r"AE GLOBAL NAMES: OK", r"AE GLOBAL NAMES: \w+ \((.*)\)", False),
    ("string tables + text fit", "text", [PY, "tools/ae_text_check.py"],
     r"AE TEXT: OK", r"AE TEXT: \w+ \((.*)\)", False),
    ("api snapshot (engine public surface)", "api", [PY, "tools/ae_api_snapshot.py", "check"],
     r"AE API: OK", r"AE API: \w+ \((.*)\)", False),
    ("entity components (D4 grep gate)", "d4", [PY, "tools/ae_d4_gate.py"],
     r"AE D4: OK", r"AE D4: \w+ \((.*)\)", False),
    ("render queue (D6 custom-draw ratchet)", "d6", [PY, "tools/ae_d6_gate.py"],
     r"AE D6: OK", r"AE D6: \w+ \((.*)\)", False),
    ("level data (data == generators)", "level", [PY, "tools/ae_level_check.py"],
     r"AE LEVEL: OK", r"AE LEVEL: \w+ \((.*)\)", False),
    ("dialogue data (validator + round-trip)", "dialogue", [PY, "tools/ae_dialogue_check.py"],
     r"AE DIALOGUE: OK", r"AE DIALOGUE: \w+ \((.*)\)", False),
    ("timeline data (validator + round-trip)", "timeline", [PY, "tools/ae_timeline_check.py"],
     r"AE TIMELINE: OK", r"AE TIMELINE: \w+ \((.*)\)", False),
    ("set3d data (validator + build)", "set3d", [PY, "tools/ae_set3d_check.py"],
     r"AE SET3D: OK", r"AE SET3D: \w+ \((.*)\)", False),
    ("unit tests", "unit", [PY, "-m", "unittest", "discover", "-s", "tests/unit", "-t", "."],
     r"^OK", r"Ran (\d+ tests?)", False),
    ("asset bake check + lint", "bake", [PY, "tools/ae_bake.py", "--check", "--lint"], r"AE BAKE: OK",
     r"AE BAKE SUMMARY: (.*)", False),
    ("smoke test", "smoke", [PY, "tools/smoke_test.py"], r"SMOKE TEST: OK", r"(SMOKE TEST: \w+)", True),
    ("golden images", "golden", [PY, "tools/ae_golden.py", "verify"], r"AE GOLDEN: OK",
     r"verified (.*)", True),
    ("replay determinism", "replay", [PY, "tools/ae_replay.py", "check"], r"AE REPLAY: OK", None, True),
    ("save snapshots reproduce replay (RPE6 P9)", "replaycheck", [PY, "tools/ae_replay_check.py"],
     r"AE REPLAY-CHECK: OK", r"AE REPLAY-CHECK: (\w+)", True),
    ("flash-reduction luminance cap (RPE6 P9)", "flash", [PY, "tools/ae_flash_check.py"],
     r"AE FLASH: OK", r"AE FLASH: (.*)", True),
    ("component dump (running M5 stage)", "dump", [PY, "tools/ae_dump_components.py", "--seg", "m5", "--seconds", "1"],
     r"AE DUMP: OK", r"AE DUMP: (segment .*)", True),
    ("main loop parity", "loop", [PY, "tools/ae_loop.py", "check"], r"AE LOOP: OK",
     r"AE LOOP: \w+ \((.*)\)", True),
    ("frame budget bench", "bench", [PY, "tools/ae_bench.py", "--check-budget"], r"AE BENCH BUDGET: OK",
     r"AE BENCH: scenario (.*)", True),
    ("3d frame budget (RPE6 P11)", "bench3d", [PY, "tools/ae_bench3d.py", "--check-budget"],
     r"AE BENCH3D BUDGET office3d: OK", r"AE BENCH3D: office3d (.*)", True),
    ("data validation (RPE6 P10)", "validate", [PY, "tools/ae_validate.py"],
     r"AE VALIDATE: OK", r"AE VALIDATE: OK \((.*)\)", True),
    ("engine3d parity - software determinism (RPE6 P10)", "engine3d", [PY, "tools/ae_engine3d_parity.py"],
     r"AE ENGINE3D PARITY: OK", r"AE ENGINE3D PARITY: OK \((.*)\)", True),
    ("mission 0 zero-engine-diff (RPE6 P10)", "mission0", [PY, "tools/ae_mission0_check.py"],
     r"AE MISSION0: OK", r"AE MISSION0: OK \((.*)\)", True),
]
TODO = []


def run_gate(label, key, cmd, ok_re, det_re):
    LOGS.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        code = r.returncode
    except subprocess.TimeoutExpired as e:
        out, code = f"TIMEOUT after {e.timeout}s", -1
    (LOGS / f"{key}.log").write_text(out, encoding="utf-8", newline="\n")
    ok = code == 0 and (ok_re is None or re.search(ok_re, out, re.M) is not None)
    det = ""
    if det_re:
        m = re.findall(det_re, out, re.M)
        det = m[-1] if m else ""
    if key == "replay":
        det = f"{len(re.findall(r'^m\d: OK', out, re.M))} segments match"
    return ok, det, time.perf_counter() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--skip", default="")
    a = ap.parse_args()
    skip = set(filter(None, a.skip.split(",")))
    rows, failed = [], False
    for label, key, cmd, ok_re, det_re, slow in GATES:
        if key in skip or (a.quick and slow):
            rows.append((label, "SKIP", ""))
            continue
        ok, det, secs = run_gate(label, key, cmd, ok_re, det_re)
        failed |= not ok
        rows.append((label, "OK" if ok else "FAIL", f"{det}  [{secs:.0f}s]".strip()))
        print(f"{label}: {'OK' if ok else 'FAIL'}", flush=True)
    for label, phase in TODO:
        rows.append((label, f"TODO (phase {phase})", ""))
    print("\nAE CI SUMMARY")
    for label, st, det in rows:
        print(f"{label} {'.' * max(2, 38 - len(label))} {st:<5} {det}")
    print("\nAE CI: FAIL" if failed else "\nAE CI: OK (implemented gates)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
