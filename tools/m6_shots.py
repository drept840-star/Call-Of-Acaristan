"""M6 3D film + interactive train stills.

    python tools/m6_shots.py [OUT_DIR] [insertion|boxcar|ending|train|train_fail|all] [--probe]
                             [--at=T1,T2,...] [--guards]

Renders every authored M6 shot (each shot dict, so both boxcar exit shots and
all four Vasile calls) at a few timestamps into OUT_DIR/<scene>_<n>_<t>.png
plus a contact sheet OUT_DIR/_sheet.jpg.  ``train`` steps the interactive
TrainScene through the canon death beat (guards cleared) and ``train_fail``
through the overrun branch; each gets its own OUT_DIR/_train*.jpg sheet.
Backend follows ACARISTAN_RENDERER (auto|gl|software); set
ACARISTAN_CUTSCENE3D=0 to review the fallbacks.

``--probe`` also prints, per frame: head-region luma (mean / p95) of every
face on screen, and for staged sets the deepest body penetration into the
set's registered solids.  Train probes add Volkov/Biribel ground clearance and
the catch hand distances.  Targets: mean 55..170, p95 < 235, penetration
<= 0.02 m.

This is a visual-review tool, not a CI gate.
"""
import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()
from core.config import HEIGHT, WIDTH  # noqa: E402
from core.cutscene_registry import set_current_shot  # noqa: E402
from core.state import STATE  # noqa: E402
from cutscenes import m6films  # noqa: E402
from cutscenes import m6world3d as w  # noqa: E402
from missions.m6 import meta  # noqa: E402


def _films_of(shots):
    return [s for s in shots if s["scene"] != "title_card"]


GROUPS = {
    "insertion": _films_of(meta.mission6_intro_shots),
    "boxcar": _films_of(meta.M6_MID_CUTSCENES["boxcar"]),
    "ending": _films_of(meta.mission6_ending_shots),
}
SET_OF = {"m6_boxcar": "boxcar", "m6_customs": "terminal", "m6_radio": "terminal"}
FRACS = (0.08, 0.42, 0.72, 0.94)
TW, TH = 320, 180
COLS = 4

# Canon: scope hit, recoil, contact, lower, settle, held breath, doors, pull.
TRAIN_AT = (2.0, 12.0, 20.0, 22.9, 23.7, 25.7, 25.95, 26.2, 26.55,
            27.0, 27.45, 28.75, 29.5, 30.6, 31.6, 32.6, 34.8, 36.6, 38.2)
# Overrun: the failure branch freezes t at SHOT_AT; these are fail-clock times.
TRAIN_FAIL_AT = (22.9, 23.05, 23.25, 23.55, 23.95, 24.35, 24.7)


def _set_key(scene):
    for pre, key in SET_OF.items():
        if scene.startswith(pre):
            return key
    return None


def _boxes(scene, t):
    """Registered blocking volumes the frame must clear: the set AABBs plus
    the airframe (local AABBs transformed with the shot's heli placement)."""
    base = scene.split("#")[0]
    boxes = dict(w.solids(_set_key(base)) or {})
    heli = m6films.heli_at(base, t)
    if heli is not None:
        boxes.update(w.heli_solids(*heli))
    return boxes


def _probe(surface, scene, t, second=None):
    parts = []
    for h in w.head_stats(surface):
        name = h["key"] if isinstance(h["key"], str) else h["key"][0]
        flag = "" if 55 <= h["mean"] <= 170 and h["p95"] < 235 else " !!"
        parts.append("%s face %.0f/%.0f f%.2f%s" % (name, h["mean"], h["p95"],
                                                    h["facing"], flag))
    boxes = _boxes(scene, t)
    if boxes:
        for a in w.LAST:
            d, part, box = w.penetration(w.hum(a["key"]), a["pose"], a["pos"],
                                         a["yaw"], boxes)
            if d > 0.004:
                name = a["key"] if isinstance(a["key"], str) else a["key"][0]
                parts.append("%s %s in %s %.3f%s" % (name, part, box, d,
                                                     " !!" if d > 0.02 else ""))
    base = scene.split("#")[0]
    metrics = m6films.walk_metrics(base, second)
    if metrics is not None:
        slip = w.walk_slip(*metrics)
        bad = max(slip.values()) > 0.02
        parts.append("slip l%.3f r%.3f%s" % (slip["l"], slip["r"],
                                             " !!" if bad else ""))
    print("  %-22s %5d  %s" % (scene, t, "  ".join(parts) or "-"))


def _film_sheet(surface, out, groups, probe=False):
    shots = [s for g in groups for s in GROUPS[g]]
    sheet = pygame.Surface((TW * len(FRACS), TH * max(1, len(shots))))
    seen = {}
    for row, shot in enumerate(shots):
        scene = shot["scene"]
        n = seen[scene] = seen.get(scene, -1) + 1
        set_current_shot(shot)
        dur = shot.get("min_ms", 5000)
        for col, f in enumerate(FRACS):
            t = int(dur * f)
            m6films.M6_3D_SCENES[scene](surface, t)
            if probe:
                _probe(surface, scene + ("#%d" % n if n else ""), t,
                       second=(n == 1) if scene == "m6_boxcar_exit" else None)
            pygame.image.save(surface, os.path.join(
                out, "%s_%d_%05d.png" % (scene, n, t)))
            sheet.blit(pygame.transform.smoothscale(surface, (TW, TH)),
                       (col * TW, row * TH))
    set_current_shot(None)
    return sheet, len(shots)


def _train_sheet(frames, out, name):
    rows = max(1, (len(frames) + COLS - 1) // COLS)
    sheet = pygame.Surface((TW * COLS, TH * rows))
    font = pygame.font.Font(None, 22)
    for i, (label, surf) in enumerate(frames):
        tile = pygame.transform.smoothscale(surf, (TW, TH))
        sheet.blit(tile, ((i % COLS) * TW, (i // COLS) * TH))
        img = font.render(label, True, (236, 226, 198))
        sheet.blit(img, ((i % COLS) * TW + 8, (i // COLS) * TH + 8))
        pygame.image.save(surf, os.path.join(out, "%s_%s.png" % (name, label)))
    pygame.image.save(sheet, os.path.join(out, "_%s.jpg" % name))


def _train_probe(surface, scene, t, sc, death):
    from missions.m6 import train3d as T
    from cutscenes import m6world3d as W
    import numpy as np
    parts = []
    for h in W.head_stats(surface, T._renderer(), full=True):
        key = h["key"] if isinstance(h["key"], str) else h["key"][0]
        flag = "" if 55 <= h["mean"] <= 170 and h["p95"] < 235 else " !!"
        parts.append("%s face %.0f/%.0f f%.2f%s" % (
            key, h["mean"], h["p95"], h["facing"], flag))
    arr = pygame.surfarray.array3d(surface).astype(float)
    pic = arr[:, 54:646]
    lum = 0.299 * pic[..., 0] + 0.587 * pic[..., 1] + 0.114 * pic[..., 2]
    ch = pic.max(axis=2) - pic.min(axis=2)
    roi = arr[300:850, 120:620]
    rlum = 0.299 * roi[..., 0] + 0.587 * roi[..., 1] + 0.114 * roi[..., 2]
    rch = roi.max(axis=2) - roi.min(axis=2)
    parts.append("pic p5/50/95 %.0f/%.0f/%.0f chroma %.1f roi %.0f/%.1f" % (
        np.percentile(lum, 5), np.percentile(lum, 50),
        np.percentile(lum, 95), ch.mean(), np.median(rlum), rch.mean()))
    if death:
        vpos, vpose, vyaw, vj = T._volkov_death_state(t, sc.volkov_delay)
        low, _ = _lowest(W.hum("volkov"), vpose, vpos, vyaw)
        parts.append("v_low %.3f chest %.2f" % (low, vj["chest"][1]))
        b = T._biribel_catch_state(t, (vpos, vpose, vyaw, vj))
        if b is not None:
            bpos, byaw, bpose = b
            blow, bj = _lowest(W.hum(("biribel", T.OUTFIT_GUARD)),
                               bpose, bpos, byaw)
            rt = (vj["chest"][0] + 0.22, vj["chest"][1] + 0.08,
                  vj["chest"][2] + 0.12)
            lt = (vj["lhand"][0] + 0.02, vj["lhand"][1] + 0.02,
                  vj["lhand"][2] + 0.04)
            planar = math.hypot(bj["pelvis"][0] - vj["head"][0],
                                bj["pelvis"][2] - vj["head"][2])
            parts.append("b_low %.3f hands sh%.2f hd%.2f sep%.2f" % (
                blow, _dist(bj["rhand"], rt), _dist(bj["lhand"], lt),
                planar))
    print("  %-22s %5d  %s" % (scene, t, "  ".join(parts) or "-"))


def _lowest(hum, pose, pos, yaw):
    verts, _faces, joints = hum.build(pose, pos, yaw, rifle_on=False)
    return min(v[1] for v in verts), joints


def _dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def _train(surface, out, fail=False, probe=False, at=None, guards=False):
    """``at``: override the sampled clock times; ``guards``: keep the roster
    alive (combat stills) instead of clearing the lane for the canon death."""
    from missions import m6
    from missions.m6 import train3d
    import core.save_system as _save

    try:
        _save.select_slot(0)
    except Exception:
        pass
    m6.start_mission6_train_checkpoint()
    sc = train3d.scene()
    if STATE.player is not None:
        STATE.player.max_hp = STATE.player.hp = 100000
    if not fail and not guards:
        sc.guards.clear()
    targets = tuple(at) if at else (TRAIN_FAIL_AT if fail else TRAIN_AT)
    frames = []
    for target in targets:
        guard = 0
        while guard < 8000:
            if fail:
                clock = sc.t + sc.fail_t
            else:
                clock = sc.t
            if clock >= target:
                break
            STATE.dt = 1.0 / 60.0
            train3d.update(None, (WIDTH // 2, HEIGHT // 2))
            STATE.dt = 0.0
            guard += 1
        train3d.draw(surface)
        clock = sc.t + (sc.fail_t if fail else 0.0)
        label = "%05.2f" % clock
        if probe:
            _train_probe(surface, "train_fail" if fail else "train",
                         clock, sc, not fail and clock >= train3d.HIT_AT)
        frames.append((label, surface.copy()))
    _train_sheet(frames, out, "train_fail" if fail else "train")
    if train3d.active():
        train3d.force_finish("tool")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    probe = "--probe" in sys.argv
    out = args[0] if args else os.path.join(ROOT, "shots", "m6")
    which = args[1] if len(args) > 1 else "all"
    groups = list(GROUPS) + ["train"] if which == "all" else [which]
    for g in groups:
        if g not in GROUPS and g not in ("train", "train_fail"):
            print("unknown group %r (use insertion|boxcar|ending|train|train_fail|all)" % g)
            return 1
    os.makedirs(out, exist_ok=True)
    surface = pygame.Surface((WIDTH, HEIGHT))
    film_groups = [g for g in groups if g in GROUPS]
    sheet = pygame.Surface((TW * COLS, TH))
    row = 0
    if film_groups:
        sheet, row = _film_sheet(surface, out, film_groups, probe)
        pygame.image.save(sheet, os.path.join(out, "_sheet.jpg"))
    at = None
    for a in sys.argv[1:]:
        if a.startswith("--at="):
            at = [float(x) for x in a[5:].split(",") if x]
    guards = "--guards" in sys.argv
    if "train" in groups:
        _train(surface, out, fail=False, probe=probe, at=at, guards=guards)
    if "train_fail" in groups:
        _train(surface, out, fail=True, probe=probe, at=at)
    if m6films._cache.get("failed"):
        print("3D FAILED:", repr(m6films._cache.get("err")))
    print("wrote", out, "(%d film rows)" % row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
