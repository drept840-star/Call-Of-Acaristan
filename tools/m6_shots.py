"""M6 3D film + interactive train stills.

    python tools/m6_shots.py [OUT_DIR] [insertion|boxcar|ending|train|train_fail|all] [--probe]
                             [--at=T1,T2,...] [--guards] [--clash]

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

``--clash`` renders no stills: it samples every film shot every 100 ms (the
train every 0.1 s) and prints each body-on-body or limb-through-own-body
overlap once, with its deepest depth and time span (!! over 0.05 m).

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
if os.environ.get("ACARISTAN_RENDERER", "").strip().lower() == "gl":
    pygame.display.set_mode((64, 64))
from core.config import HEIGHT, WIDTH  # noqa: E402
from core.cutscene_registry import scene_renderer, set_current_shot  # noqa: E402
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
    if scene in ("m6_radio_vasile#1", "m6_radio_vasile#3"):
        return {}          # Vasile's office: no registered solids
    boxes = dict(w.solids(_set_key(base)) or {})
    if base in ("m6_helicopter", "m6_insert_cabin"):
        # The camera is inside / alongside the airframe for the pickup and
        # cabin beats; its collision AABBs are the cabin the actors sit in,
        # not obstacles.  Ground clearance is covered by the insertion tests.
        return boxes
    heli = m6films.heli_at(base, t)
    if heli is not None:
        boxes.update(w.heli_solids(*heli))
    return boxes


# Rig slots (engine3d.rig SLOTS): 0 pelvis 1 torso 2 head, then per side
# (l base 4, r base 10) +0 uarm +2 farm +3 thigh +4 shin +5 foot.
_PART = {0: "pelvis", 1: "torso", 2: "head", 4: "l_uarm", 6: "l_farm",
         7: "l_thigh", 8: "l_shin", 9: "l_foot", 10: "r_uarm", 12: "r_farm",
         13: "r_thigh", 14: "r_shin", 15: "r_foot"}
# Same-body pairs that must not interpenetrate (joint neighbours excluded).
_SELF = ((6, 1), (6, 2), (12, 1), (12, 2), (4, 2), (10, 2), (6, 12),
         (6, 13), (12, 7), (7, 13), (8, 14), (9, 15), (8, 15), (14, 9))


def _obbs(a):
    """Posed part boxes of one LAST actor: {slot: (M, org, lo, hi, sc, verts)}."""
    h = w.hum(a["key"])
    places, _j, root = h.pose_world(a["pose"], a["pos"], a["yaw"])
    uniq = h._unique_verts()
    sc = h._scale
    out = {}
    for slot, key, M, org, _g, _fb in places:
        if slot not in _PART or not uniq.get(key):
            continue
        vs = uniq[key]
        lo = tuple(min(v[i] for v in vs) for i in range(3))
        hi = tuple(max(v[i] for v in vs) for i in range(3))
        o = (org[0] + root[0], org[1] + root[1], org[2] + root[2])
        out[slot] = (M, o, lo, hi, sc, vs)
    return out


def _depth(src, dst):
    """Deepest vertex of part ``src`` inside part box ``dst``, metres."""
    M, o, _lo, _hi, _sc, vs = src
    N, p, lo, hi, sc, _v = dst
    k = 1.0 / (sc * sc)
    best = 0.0
    for x, y, z in vs:
        dx = M[0] * x + M[1] * y + M[2] * z + o[0] - p[0]
        dy = M[3] * x + M[4] * y + M[5] * z + o[1] - p[1]
        dz = M[6] * x + M[7] * y + M[8] * z + o[2] - p[2]
        lx = (N[0] * dx + N[3] * dy + N[6] * dz) * k
        ly = (N[1] * dx + N[4] * dy + N[7] * dz) * k
        lz = (N[2] * dx + N[5] * dy + N[8] * dz) * k
        d = min(lx - lo[0], hi[0] - lx, ly - lo[1], hi[1] - ly,
                lz - lo[2], hi[2] - lz) * sc
        if d > best:
            best = d
    return best


def clashes(actors=None, tol=0.02):
    """Body-on-body and limb-through-own-body overlaps among this frame's
    actors -> [(metres, "who part / who part")], deepest first."""
    actors = w.LAST if actors is None else actors
    boxes = [(_name(a), _obbs(a)) for a in actors]
    hits = []
    for name, ob in boxes:
        for s1, s2 in _SELF:
            if s1 in ob and s2 in ob:
                d = max(_depth(ob[s1], ob[s2]), _depth(ob[s2], ob[s1]))
                if d > tol:
                    hits.append((d, "%s %s / %s" % (name, _PART[s1], _PART[s2])))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (na, oa), (nb, ob) = boxes[i], boxes[j]
            for s1, b1 in oa.items():
                for s2, b2 in ob.items():
                    d = max(_depth(b1, b2), _depth(b2, b1))
                    if d > tol:
                        hits.append((d, "%s %s / %s %s" % (na, _PART[s1], nb,
                                                           _PART[s2])))
    hits.sort(reverse=True)
    return hits


def _name(a):
    return a["key"] if isinstance(a["key"], str) else a["key"][0]


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


def _report(scene, worst):
    """worst: {label: (depth, t_first, t_last, t_deepest)} -> one line each."""
    if not worst:
        print("  %-22s clean" % scene)
    for label, (d, t0, t1, tm) in sorted(worst.items(), key=lambda kv: -kv[1][0]):
        print("  %-22s %.3f m  %-34s t %s..%s (max @%s)%s" % (
            scene, d, label, t0, t1, tm, " !!" if d > 0.05 else ""))


def _note(worst, t, hits):
    for d, label in hits:
        cur = worst.get(label)
        if cur is None:
            worst[label] = (d, t, t, t)
        else:
            worst[label] = (max(d, cur[0]), cur[1], t,
                            t if d > cur[0] else cur[3])


def _clash_films(surface, groups, step=100):
    """Every shot sampled every ``step`` ms; prints each clashing pair once
    with its depth and time span."""
    seen = {}
    for shot in (s for g in groups for s in GROUPS[g]):
        scene = shot["scene"]
        n = seen[scene] = seen.get(scene, -1) + 1
        set_current_shot(shot)
        fn = scene_renderer(scene) or m6films.M6_3D_SCENES[scene]
        worst = {}
        for t in range(0, shot.get("min_ms", 5000), step):
            fn(surface, t)
            _note(worst, t, clashes())
        _report(scene + ("#%d" % n if n else ""), worst)
    set_current_shot(None)


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
            fn = scene_renderer(scene) or m6films.M6_3D_SCENES[scene]
            fn(surface, t)
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


def _train(surface, out, fail=False, probe=False, at=None, guards=False,
           clash=None):
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
        if clash is not None:
            _note(clash, "%.2f" % clock, clashes())
            continue
        label = "%05.2f" % clock
        if probe:
            _train_probe(surface, "train_fail" if fail else "train",
                         clock, sc, not fail and clock >= train3d.HIT_AT)
        frames.append((label, surface.copy()))
    if clash is not None:
        _report("train_fail" if fail else "train", clash)
    else:
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
    if "--clash" in sys.argv:
        _clash_films(surface, film_groups)
        for g in ("train", "train_fail"):
            if g in groups:
                fail = g == "train_fail"
                lo, hi = (22.9, 24.8) if fail else (1.0, 39.0)
                ts = [round(lo + 0.1 * i, 2) for i in range(int((hi - lo) / 0.1) + 1)]
                _train(surface, out, fail=fail, at=ts, clash={})
        return 0
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
