"""RPE6 golden-image harness (master prompt §9). Phase 0: capture + verify.

    python tools/ae_golden.py capture [--set baseline_v0] [--only SUBSTR] [--kinds cutscene,gameplay]
    python tools/ae_golden.py verify  [--set baseline_v0] [--only SUBSTR] [--kinds ...]

`--only SUBSTR` filters what is recorded/compared, never what is rendered: every
spec still renders so a partial recapture stays in the full-sequence state. Gameplay
shots inherit FX/cache state from earlier renders (M5 rain/fire), so recording one in
an isolated render produces a hash its own verify can never match (2026-10-15 fix).

Captures, with the *current* legacy code:
  * cutscene: every shot of every shot list (engine.cutscene1/2_shots + every
    missions.mN.meta list of {scene: ...} dicts) at 25 %, 50 %, 75 % of its
    on-screen duration, through the real player composite (scene + vignette +
    scanlines + letterbox + dialogue box) - same composite as m5_gauntlet_cycle;
  * gameplay: the M5 top-down gauntlet shots (m5_gauntlet_shots td) and the
    three M3 stills from tools/golden.py.
Determinism: ACA_FREEZE=1, random.seed(SEED) before every shot, software 3D
backend by default (canonical oracle, ADR-006). Output:
  tests/golden/<set>/<id>.png + manifest.json {id, kind, source, t_ms, seed,
  renderer, resolution, settings_profile, sha256}
verify re-renders and compares: 2D gameplay = exact; 3D cutscene = <=0.5 % of
pixels with diff > 8 and mean diff <= 0.6. Baseline PNGs are optional: verify
  compares manifest sha256 first and only opens a PNG when a hash differs (without
  it the shot fails as 'hash differs; baseline png missing'; run `capture` to get
  PNGs back). The sandbox keeps manifest.json only (ADR-006, 28 MB saved).
  Failures write <id>.diff.png heatmaps
under tests/golden/_verify/<set>/. Prints `AE GOLDEN: OK` / `AE GOLDEN: FAIL`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("ACARISTAN_RENDERER", "software")
os.environ["ACARISTAN_CUTSCENE3D"] = "1"
os.environ["ACA_FREEZE"] = "1"
# Sandbox saves/settings/profile (*_aetools.json). Before B-010 this happened
# by accident because importing missions.m3 redirected them to a temp dir.
os.environ.setdefault("ACA_SAVE_SUFFIX", "_aetools")
ROOT = Path(__file__).resolve().parent.parent

# Hash-seed pin (BUGS B-011, withdrawn): the oracle re-executes itself with
# PYTHONHASHSEED=0 so record and check always share one str-hash order. This is
# belt and braces, not a known dependence: the full replay matches baseline_v0
# under seeds 0, 1, 7 and random (2026-10-14). The divergence first blamed on
# hashing was B-012 (cold vs warm radio cache). AE_NO_HASHSEED_PIN=1 runs unpinned.
if os.environ.get("PYTHONHASHSEED") != "0" and not os.environ.get("AE_NO_HASHSEED_PIN"):
    import subprocess as _sp
    sys.exit(_sp.call([sys.executable, *sys.argv], env=dict(os.environ, PYTHONHASHSEED="0")))
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pygame  # noqa: E402

# Pin the wall clock BEFORE any game import (some modules bind get_ticks at
# import). Gameplay draw code reads pygame.time.get_ticks()/time.time() for
# rain/flicker/pulses even under ACA_FREEZE (BUGS.md B-001); unpinned, 9 of 14
# gameplay shots differ run-to-run. Cutscenes are driven by t_ms and are
# unaffected. Remove once the fixed-step clock (Phase 1) owns time.
PINNED_TICKS_MS, PINNED_EPOCH_S = 100_000, 1_700_000_000.0
pygame.time.get_ticks = lambda: PINNED_TICKS_MS
time.time = lambda: PINNED_EPOCH_S

pygame.init()
from core import config as cfg  # noqa: E402
from core.config import HEIGHT, WIDTH  # noqa: E402
from core.state import STATE  # noqa: E402

SEED = 1337
CHAR_MS = 28
FRACTIONS = (0.25, 0.50, 0.75)
TOL_3D_PCT, TOL_3D_MEAN, PIX_THRESH = 0.5, 0.6, 8
T = cfg.TILE_SIZE


# ------------------------------------------------------------------ shot lists
def cutscene_lists():
    """[(list_id, [shot dicts])], deduplicated by list identity, stable order."""
    import importlib
    from cutscenes import engine as eng
    out, seen = [], set()

    def add(lid, v):
        if isinstance(v, dict):
            if not all(isinstance(x, list) for x in v.values()):
                return
            shots = sum(v.values(), [])
        else:
            shots = list(v)
        if not shots or not all(isinstance(s, dict) and "scene" in s for s in shots):
            return
        key = tuple(id(s) for s in shots)
        if key in seen:
            return
        seen.add(key)
        out.append((lid, shots))

    add("m1.cutscene1", eng.cutscene1_shots)
    add("m1.cutscene2", eng.cutscene2_shots)
    for m in ("m2", "m3", "m4", "m5"):
        for part in ("meta", "flow"):      # m3.flow owns chair_break_shots
            try:
                meta = importlib.import_module(f"missions.{m}.{part}")
            except Exception:  # noqa: BLE001
                continue
            for name in sorted(vars(meta)):
                v = getattr(meta, name)
                if isinstance(v, (list, tuple, dict)) and not name.startswith("__"):
                    add(f"{m}.{name}", v)
    return out


def duration(s) -> int:
    txt = s.get("text") or ""
    return int(max(s.get("min_ms", 3000), len(txt) * CHAR_MS + 900))


def composite(surf, s, t):
    from cutscenes import engine as eng
    eng.draw_cutscene_scene(surf, s, t)
    cfg.draw_vignette(surf, strength=80 if s.get("quiet_ui") else 180)
    if not s.get("quiet_ui"):
        cfg.draw_scanlines(surf)
    cfg.draw_letterbox(surf)
    txt = s.get("text") or ""
    if t >= s.get("caption_after_ms", 0) and not s.get("hide_caption") and (txt or s.get("speaker")):
        ci = min(len(txt), max(0, t - s.get("caption_after_ms", 0)) // CHAR_MS)
        eng.draw_dialogue_box(surf, s.get("speaker"), txt, ci, len(txt), t >= s.get("min_ms", 0))


def cutscene_specs():
    for lid, shots in cutscene_lists():
        for i, s in enumerate(shots):
            d = duration(s)
            for f in FRACTIONS:
                t = int(d * f)
                sid = f"cut.{lid}.{i:02d}_{s['scene']}.t{int(f * 100):02d}"

                def render(surf, s=s, t=t):
                    try:
                        from cutscenes import engine as eng
                        eng.reset_dialogue_slide()
                    except Exception:  # noqa: BLE001
                        pass
                    composite(surf, s, t)
                yield {"id": sid, "kind": "cutscene", "source": f"{lid}[{i}] scene={s['scene']}",
                       "t_ms": t, "render": render}


# gameplay: sequential (state carries between shots), so one generator
def gameplay_specs():
    screen = cfg.screen

    def blit_screen(surf):
        surf.blit(screen, (0, 0))

    # --- M5 top-down gauntlet (mirrors tools/m5_gauntlet_shots.py topdown())
    def m5_seq():
        import missions.m5 as m5
        from missions.m5 import draw, flow, quarter, world
        m5.start_m5()

        from core import game_core as _gc

        def shot(name, wx, wy, frames=3):
            STATE.player.rect.center = (int(wx), int(wy))
            cx, cy = wx - WIDTH // 2, wy - HEIGHT // 2
            for _ in range(frames):
                _gc.game_draw(cx, cy)   # RPE6 Phase 6: through the hosted draw path (same pixels as draw.game_draw)
            return {"id": f"gp.m5.{name}", "kind": "gameplay", "source": f"m5 gauntlet td:{name}",
                    "t_ms": None, "render": blit_screen}

        flow._enter_hq()
        yield shot("hq_west", 4 * T, 11 * T)
        yield shot("hq_east", 20 * T, 8 * T)
        yield shot("hq_office", 24 * T, 5 * T)
        flow._start_vasile_dialogue()
        flow._m5_dlg["char_idx"] = 9999
        yield shot("dialogue", 24 * T, 5 * T)
        flow._dlg_reset()
        STATE.m5_dialogue_active = False
        flow._enter_quarter()
        yield shot("quarter_start", 6 * T, 15 * T)
        for i in range(300):
            STATE.player.rect.center = (int((6 + i * 0.06) * T), 15 * T)
            quarter.update()
        yield shot("quarter_mid", 22 * T, 15 * T)
        yield shot("quarter_east", 33 * T, 15 * T)
        flow._enter_printworks()
        px, py = STATE.player.rect.center
        yield shot("print_entry", px, py)
        mp = world._maru_office_pos()
        yield shot("print_maru", mp[0] - 40, mp[1] + 20)
        flow._begin_raid()
        from missions.m5 import systems

        class _NoKeys:
            def __getitem__(self, k):
                return False
        for _ in range(90):
            systems.game_update(_NoKeys())
        yield shot("print_raid", mp[0] - 40, mp[1] + 60)
        flow._enter_tunnel()
        px, py = STATE.player.rect.center
        yield shot("tunnel", px + 120, py)

    # --- M3 stills (mirrors tools/golden.py)
    def m3_seq():
        from core import game_core as gc
        from missions import m3
        from missions.m3 import world as w

        def cam(tx, ty):
            STATE.player.rect.center = (int(tx * T), int(ty * T))
            return m3._clamp_m3_camera(int(tx * T - WIDTH // 2), int(ty * T - HEIGHT // 2))

        def still(name, setup):
            fcx, fcy = setup()
            screen.fill((0, 0, 0))
            gc.game_draw(fcx, fcy)
            gc.game_draw(fcx, fcy)
            return {"id": f"gp.m3.{name}", "kind": "gameplay", "source": f"tools/golden.py:{name}",
                    "t_ms": None, "render": blit_screen}

        def archives():
            m3.start_mission3_archives_checkpoint(preserve_timer=True)
            return cam(12, 27)

        def comms():
            m3.start_mission3_comms_checkpoint(preserve_timer=True)
            return cam(w._RELAY_TILE_COL - 2, w._RELAY_TILE_ROW - 2)

        def cell():
            gc.start_mission3_breakout_checkpoint(preserve_timer=True)
            cx, cy = m3._interrogation_chair_pos()
            return cam(cx // T + 3, cy // T + 2)
        for n, f in (("archives", archives), ("comms", comms), ("cell", cell)):
            random.seed(SEED)
            yield still(n, f)

    # --- M1 / M2 / M4 stills + extra M3 maps (added with the Phase 3 layer conversion so every
    # staticlayer bake callback has a pixel oracle; captured BEFORE the first conversion).
    def _still(mid, name, setup):
        fcx, fcy = setup()
        screen.fill((0, 0, 0))
        from core import game_core as gc
        gc.game_draw(fcx, fcy)
        gc.game_draw(fcx, fcy)
        return {"id": f"gp.{mid}.{name}", "kind": "gameplay", "source": f"ae_golden:{mid}.{name}",
                "t_ms": None, "render": blit_screen}

    def _cam_at(tx, ty):
        STATE.player.rect.center = (int(tx * T), int(ty * T))
        return int(tx * T - WIDTH // 2), int(ty * T - HEIGHT // 2)

    def m1_seq():
        from core import game_core as gc

        def start():
            gc.start_mission(preserve_timer=True)
            px, py = STATE.player.rect.center
            return int(px - WIDTH // 2), int(py - HEIGHT // 2)
        yield _still("m1", "start", start)
        yield _still("m1", "desks", lambda: _cam_at(14, 9))
        yield _still("m1", "warehouse", lambda: _cam_at(30, 14))

    def m2_seq():
        from core import game_core as gc

        def start():
            gc.start_mission2(preserve_timer=True)
            px, py = STATE.player.rect.center
            return int(px - WIDTH // 2), int(py - HEIGHT // 2)

        def checkpoint():
            gc.start_mission2_checkpoint(preserve_timer=True)
            px, py = STATE.player.rect.center
            return int(px - WIDTH // 2), int(py - HEIGHT // 2)
        yield _still("m2", "start", start)
        yield _still("m2", "road_east", lambda: _cam_at(40, 12))
        yield _still("m2", "checkpoint", checkpoint)
        yield _still("m2", "garden", lambda: _cam_at(20, 30))

    def m4_seq():
        from core import game_core as gc

        def street():
            gc.start_mission4(preserve_timer=True)
            px, py = STATE.player.rect.center
            return int(px - WIDTH // 2), int(py - HEIGHT // 2)

        def station():
            gc.start_mission4_station_checkpoint(preserve_timer=True)
            px, py = STATE.player.rect.center
            return int(px - WIDTH // 2), int(py - HEIGHT // 2)
        yield _still("m4", "street", street)
        yield _still("m4", "street_east", lambda: _cam_at(30, 10))
        yield _still("m4", "station", station)

    def m3_more_seq():
        from core import game_core as gc
        from missions import m3

        def cam(tx, ty):
            STATE.player.rect.center = (int(tx * T), int(ty * T))
            return m3._clamp_m3_camera(int(tx * T - WIDTH // 2), int(ty * T - HEIGHT // 2))

        def corridor():
            gc.start_mission3_breakout_checkpoint(preserve_timer=True)
            return cam(14, 14)

        def maintenance():
            gc.start_mission3_breakout_checkpoint(preserve_timer=True)
            return cam(36, 36)

        def kill_order():
            gc.start_mission3_kill_order_checkpoint(preserve_timer=True)
            px, py = STATE.player.rect.center
            return m3._clamp_m3_camera(int(px - WIDTH // 2), int(py - HEIGHT // 2))

        def broadcast():
            gc.start_mission3_broadcast_checkpoint(preserve_timer=True)
            px, py = STATE.player.rect.center
            return m3._clamp_m3_camera(int(px - WIDTH // 2), int(py - HEIGHT // 2))
        yield _still("m3", "corridor", corridor)
        yield _still("m3", "maintenance", maintenance)
        yield _still("m3", "kill_order", kill_order)
        yield _still("m3", "broadcast", broadcast)

        # Tier B oracles (captured before the per-frame painters were baked): the three
        # neighbour cells, the kitchen, the Kill Order dock / van.
        def cellblock_cam(tx, ty):
            def f():
                gc.start_mission3_breakout_checkpoint(preserve_timer=True)
                return cam(tx, ty)
            return f

        def ko_cam(tx, ty):
            def f():
                gc.start_mission3_kill_order_checkpoint(preserve_timer=True)
                return cam(tx, ty)
            return f
        yield _still("m3", "cell_a", cellblock_cam(10, 9))
        yield _still("m3", "cell_b", cellblock_cam(18, 9))
        yield _still("m3", "cell_c", cellblock_cam(26, 9))
        yield _still("m3", "kitchen", cellblock_cam(5, 22))
        yield _still("m3", "ko_dock", ko_cam(10, 34))
        yield _still("m3", "ko_van", ko_cam(31, 36))

    for seq in (m5_seq, m3_seq, m1_seq, m2_seq, m4_seq, m3_more_seq):
        random.seed(SEED)
        gen = seq()
        while True:
            try:
                spec = next(gen)
            except StopIteration:
                break
            except Exception as e:  # noqa: BLE001
                yield {"id": f"gp.{seq.__name__}.ERROR", "kind": "gameplay", "error": repr(e),
                       "trace": traceback.format_exc(limit=4)}
                break
            yield spec


# ------------------------------------------------------------------ compare
def surf_array(surf) -> np.ndarray:
    return pygame.surfarray.array3d(surf).astype(np.int16)


def compare(a: np.ndarray, b: np.ndarray):
    if a.shape != b.shape:
        return {"shape_mismatch": True, "max": 255, "mean": 255.0, "pct_over": 100.0}, None
    d = np.abs(a - b).max(axis=2)
    return {"max": int(d.max()), "mean": round(float(d.mean()), 4),
            "pct_over": round(float((d > PIX_THRESH).mean() * 100), 4),
            "differing_px": int((d > 0).sum())}, d


def passes(kind: str, st: dict) -> bool:
    if st.get("shape_mismatch"):
        return False
    if kind == "cutscene":
        return st["pct_over"] <= TOL_3D_PCT and st["mean"] <= TOL_3D_MEAN
    return st["differing_px"] == 0


def heatmap(d: np.ndarray, path: Path):
    h = np.clip(d * 4, 0, 255).astype(np.uint8)
    rgb = np.stack([h, (h // 3), np.zeros_like(h)], axis=2)
    pygame.image.save(pygame.surfarray.make_surface(rgb), str(path))


# ------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("capture", "verify", "list"))
    ap.add_argument("--set", default=os.environ.get("ACA_GOLDEN_SET", "baseline_v0"),
                    help="baseline set under tests/golden/ (env ACA_GOLDEN_SET; sandbox sets are machine-specific)")
    ap.add_argument("--only", default="")
    ap.add_argument("--kinds", default="cutscene,gameplay")
    ap.add_argument("--merge", action="store_true", help="capture: keep existing baseline shots, add/replace the captured ones")
    a = ap.parse_args()
    kinds = set(a.kinds.split(","))
    gdir = ROOT / "tests" / "golden" / a.set
    vdir = ROOT / "tests" / "golden" / "_verify" / a.set
    surf = pygame.Surface((WIDTH, HEIGHT))
    renderer = os.environ.get("ACARISTAN_RENDERER", "software")
    manifest = {}
    if a.mode == "verify":
        mp = gdir / "manifest.json"
        if not mp.exists():
            print(f"AE GOLDEN: FAIL no manifest at {mp}")
            return 1
        manifest = json.loads(mp.read_text(encoding="utf-8"))
        vdir.mkdir(parents=True, exist_ok=True)
    else:
        gdir.mkdir(parents=True, exist_ok=True)

    specs = []
    if "cutscene" in kinds:
        specs.append(cutscene_specs())
    if "gameplay" in kinds:
        specs.append(gameplay_specs())
    entries, fails, errors, n = {}, [], [], 0
    t_start = time.perf_counter()
    for gen in specs:
        for spec in gen:
            sid = spec["id"]
            wanted = not a.only or a.only in sid
            if a.mode == "list":
                if wanted:
                    print(sid)
                continue
            if "error" in spec:
                if wanted:
                    errors.append((sid, spec["error"]))
                    print(f"ERROR {sid}: {spec['error']}\n{spec['trace']}")
                continue
            # --only filters what is recorded (or compared), never what is rendered:
            # gameplay shots inherit FX/cache state from earlier renders, so skipping
            # renders would record them in a state the full sequence never sees.
            random.seed(SEED)
            surf.fill((0, 0, 0))
            try:
                spec["render"](surf)
            except Exception as e:  # noqa: BLE001
                if wanted:
                    errors.append((sid, repr(e)))
                    print(f"ERROR {sid}: {e!r}\n{traceback.format_exc(limit=3)}")
                continue
            if not wanted:
                continue
            raw = pygame.image.tobytes(surf, "RGB")
            sha = hashlib.sha256(raw).hexdigest()
            n += 1
            if a.mode == "capture":
                pygame.image.save(surf, str(gdir / f"{sid}.png"))
                entries[sid] = {"id": sid, "kind": spec["kind"], "source": spec["source"], "t_ms": spec["t_ms"],
                                "seed": SEED, "renderer": renderer, "resolution": [WIDTH, HEIGHT],
                                "settings_profile": "default+ACA_FREEZE+pinned_clock", "sha256": sha}
            else:
                base = manifest.get("shots", {}).get(sid)
                if base is None:
                    fails.append((sid, "not in baseline"))
                    continue
                if base["sha256"] == sha:
                    continue
                png = gdir / f"{sid}.png"
                if not png.exists():
                    fails.append((sid, "hash differs; baseline png missing"))
                    continue
                st, d = compare(surf_array(pygame.image.load(str(png))), surf_array(surf))
                if not passes(spec["kind"], st):
                    fails.append((sid, st))
                    if d is not None:
                        heatmap(d, vdir / f"{sid}.diff.png")
                    pygame.image.save(surf, str(vdir / f"{sid}.now.png"))
    if a.mode == "list":
        return 0
    took = round(time.perf_counter() - t_start, 1)   # perf_counter is not pinned
    if a.mode == "capture":
        if a.merge and (gdir / "manifest.json").exists():
            prev = json.loads((gdir / "manifest.json").read_text(encoding="utf-8")).get("shots", {})
            prev.update(entries)
            entries = prev
        man = {"schema": "ae.golden.manifest", "version": 1, "set": a.set, "seed": SEED,
               "renderer": renderer, "fractions": list(FRACTIONS),
               "tolerances": {"gameplay": "exact", "cutscene": {"pct_over_8": TOL_3D_PCT, "mean": TOL_3D_MEAN}},
               "errors": [{"id": i, "error": e} for i, e in errors],
               "shots": dict(sorted(entries.items()))}
        mp = gdir / "manifest.json"
        if a.only and mp.exists():           # partial recapture merges into the manifest
            old = json.loads(mp.read_text(encoding="utf-8"))
            old["shots"].update(man["shots"])
            man["shots"] = dict(sorted(old["shots"].items()))
        mp.write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"captured {n} shots ({len(errors)} errors) in {took}s -> {gdir}")
        print("AE GOLDEN: OK" if not errors else "AE GOLDEN: CAPTURED WITH ERRORS")
        return 0 if not errors else 2
    worst = max((f for f in fails if isinstance(f[1], dict)), key=lambda f: f[1]["pct_over"], default=None)
    print(f"verified {n} shots in {took}s: {len(fails)} failures, {len(errors)} errors"
          + (f"; worst {worst[0]} {worst[1]}" if worst else ""))
    for sid, why in fails[:40]:
        print(f"  FAIL {sid}: {why}")
    ok = not fails and not errors
    print("AE GOLDEN: OK" if ok else "AE GOLDEN: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
