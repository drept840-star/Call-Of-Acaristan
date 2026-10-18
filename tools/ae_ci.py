"""RPE6 one-command CI (D10).  python tools/ae_ci.py [--quick] [--skip name,name] [--jobs N] [--serial] [--force]

Runs every gate that exists so far and prints the §13 summary table. Gates that
belong to later phases are listed as `TODO (phase N)` and do not fail the run.
Exit code is non-zero if any implemented gate fails. Logs: build/ae_ci/<gate>.log

Isolation and speed (2026-10-18):
  * Gates are independent subprocesses, so the non-timing gates run concurrently
    in a thread pool (--jobs N, default 4; --serial keeps the old strict order).
  * The frame-budget benches (`bench`, `bench3d`) are timing-sensitive: they
    always run first and alone, on a quiet machine (B-034: their p99 is
    load-sensitive).
  * Every gate gets its own save/settings/profile suffix
    (`ACA_SAVE_SUFFIX=_aeci_<gate>`) so two gates can never share the same
    scratch files (B-027: two harness runs sharing `*_aetools.json` went
    false-red under load). Tools that pin their own suffix (ae_loop `_aeloop`,
    the smoke test's temp store) are unaffected.
  * `build/ae_ci/.lock` refuses a second concurrent run of this tool (B-027
    recommendation); `--force` steals a lock a dead run left behind (> 90 min).
--quick skips the slow gates (smoke test, golden, replay, main loop).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
LOGS = ROOT / "build" / "ae_ci"
LOCK = LOGS / ".lock"
LOCK_STALE_S = 90 * 60
EXCLUSIVE = ("bench", "bench3d")   # timing-sensitive: always first, always alone
JOBS_DEFAULT = 4

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
    # B-027: one scratch suffix per gate; never the shared *_aetools.json.
    env = dict(os.environ, ACA_SAVE_SUFFIX=f"_aeci_{key}")
    t0 = time.perf_counter()
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
                           encoding="utf-8", errors="replace", env=env)
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


def _acquire_lock(force: bool):
    """None when the lock is ours; otherwise the refusal message (B-027)."""
    LOGS.mkdir(parents=True, exist_ok=True)
    if LOCK.exists() and not force:
        info = {}
        try:
            info = json.loads(LOCK.read_text(encoding="utf-8"))
        except Exception:
            pass
        started = float(info.get("started") or 0.0)
        age = time.time() - (started or LOCK.stat().st_mtime)
        if age < LOCK_STALE_S:
            return (f"another ae_ci run looks live (pid {info.get('pid', '?')}, {age / 60:.0f} min old)"
                    f" - refusing to share build/ae_ci and the repo scratch dirs (B-027);"
                    f" use --force to steal the lock, or delete {LOCK}")
    LOCK.write_text(json.dumps({"pid": os.getpid(), "started": time.time()}), encoding="utf-8")
    return None


def _release_lock() -> None:
    try:
        info = json.loads(LOCK.read_text(encoding="utf-8"))
        if int(info.get("pid", -1)) == os.getpid():
            LOCK.unlink()
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--skip", default="")
    ap.add_argument("--jobs", type=int, default=JOBS_DEFAULT,
                    help=f"parallel gates (default {JOBS_DEFAULT}; 1 keeps the old order)")
    ap.add_argument("--serial", action="store_true", help="run one gate at a time, in the listed order")
    ap.add_argument("--force", action="store_true", help="steal the run lock left behind by a dead run")
    a = ap.parse_args()
    skip = set(filter(None, a.skip.split(",")))
    refused = _acquire_lock(a.force)
    if refused:
        print(f"AE CI: {refused}")
        return 2
    try:
        jobs = 1 if a.serial else max(1, min(a.jobs, os.cpu_count() or 1))
        rows_todo = [(label, key, cmd, ok_re, det_re) for label, key, cmd, ok_re, det_re, slow in GATES
                     if key not in skip and not (a.quick and slow)]
        done = {}
        for label, key, cmd, ok_re, det_re, slow in GATES:
            if key in skip or (a.quick and slow):
                done[key] = ("SKIP", "")

        def _one(row):
            label, key, cmd, ok_re, det_re = row
            ok, det, secs = run_gate(label, key, cmd, ok_re, det_re)
            return key, label, ("OK" if ok else "FAIL"), f"{det}  [{secs:.0f}s]".strip()

        def _finish(res):
            key, label, st, det = res
            done[key] = (st, det)
            print(f"{label}: {st}", flush=True)

        for row in [r for r in rows_todo if r[1] in EXCLUSIVE]:   # benches: quiet machine first
            _finish(_one(row))
        pooled = [r for r in rows_todo if r[1] not in EXCLUSIVE]
        if jobs == 1:
            for row in pooled:
                _finish(_one(row))
        elif pooled:
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                for fut in as_completed([pool.submit(_one, row) for row in pooled]):
                    _finish(fut.result())

        rows, failed = [], False
        for label, key, cmd, ok_re, det_re, slow in GATES:
            st, det = done.get(key, ("SKIP", ""))
            failed |= st == "FAIL"
            rows.append((label, st, det))
        for label, phase in TODO:
            rows.append((label, f"TODO (phase {phase})", ""))
        print("\nAE CI SUMMARY")
        for label, st, det in rows:
            print(f"{label} {'.' * max(2, 38 - len(label))} {st:<5} {det}")
        print("\nAE CI: FAIL" if failed else "\nAE CI: OK (implemented gates)")
        return 1 if failed else 0
    finally:
        _release_lock()


if __name__ == "__main__":
    sys.exit(main())
