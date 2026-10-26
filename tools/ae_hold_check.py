"""Weapon hold + arm self-collision gate for the 3D cutscenes.

    python tools/ae_hold_check.py [--baseline] [--samples=N] [--top=N]

Renders every M6 film shot and every M5 3D scene at N times across its length,
records each armed actor the renderer poses, and checks engine3d.hold.hold_report:
support-hand gap < 1.5 cm, arm and rifle penetration into the body < 3 cm.
Prints the worst offenders by shot and time; ``AE HOLD: OK`` when none.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["ACARISTAN_RENDERER"] = "software"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import pygame  # noqa: E402

pygame.init()
from core.config import HEIGHT, WIDTH  # noqa: E402
from engine3d import hold  # noqa: E402
from engine3d.rig import Humanoid  # noqa: E402

GAP_MAX, DEPTH_MAX = 0.015, 0.03
_seen = {}
_busy = [False]


def _record(hum, pose, pos, yaw, rifle_on):
    if _busy[0] or not rifle_on or getattr(hum, "_rifle", None) is None:
        return
    # last pose wins per rig: solvers pose it repeatedly before the draw
    _seen[id(hum)] = (hum, dict(pose), tuple(pos), yaw)


def _install():
    build, pw = Humanoid.build, Humanoid.pose_world

    def b(self, pose, pos, yaw, rifle_on=True, *a, **k):
        _record(self, pose, pos, yaw, rifle_on)
        return build(self, pose, pos, yaw, rifle_on, *a, **k)

    def p(self, pose, pos, yaw, rifle_on=True, *a, **k):
        _record(self, pose, pos, yaw, rifle_on)
        return pw(self, pose, pos, yaw, rifle_on, *a, **k)

    Humanoid.build, Humanoid.pose_world = b, p
    return pw


_weapon = hold.weapon_of


def _check(label, t, rows, pw):
    _busy[0] = True
    try:
        for hum, pose, pos, yaw in list(_seen.values()):
            rep = hold.hold_report(hum, pose, pos, yaw, _weapon(hum))
            worst = max((rep["support"] or 0.0) - (GAP_MAX - DEPTH_MAX), rep["arm"], rep["rifle"] or 0.0)
            bad = ((rep["support"] or 0.0) > GAP_MAX or rep["arm"] > DEPTH_MAX
                   or (rep["rifle"] or 0.0) > DEPTH_MAX)
            if bad:
                rows.append((worst, label, t, rep))
    finally:
        _busy[0] = False
        _seen.clear()


def _m6(surface, n, rows, pw):
    import m6_shots as ms
    from core.cutscene_registry import scene_renderer, set_current_shot
    from cutscenes import m6films
    counts = {}
    for g, shots in ms.GROUPS.items():
        for shot in shots:
            scene = shot["scene"]
            i = counts[scene] = counts.get(scene, -1) + 1
            set_current_shot(shot)
            fn = scene_renderer(scene) or m6films.M6_3D_SCENES[scene]
            dur = shot.get("min_ms", 5000)
            for k in range(n):
                t = int(dur * (k + 0.5) / n)
                fn(surface, t)
                _check("m6 %s#%d" % (scene, i), t, rows, pw)
    set_current_shot(None)


def _m5(surface, n, rows, pw):
    import m5_shots as m5
    from cutscenes import m5martial3d as m3d
    from cutscenes import m5mid3d as mid
    takes = list(m3d.M5_3D_SCENES.items()) + list(mid.M5X_SCENES.items())
    for name, fn in takes:
        dur = m5.DUR.get(name, m5.DEFAULT)
        for k in range(n):
            t = int(dur * (k + 0.5) / n)
            fn(surface, t)
            _check("m5 %s" % name, t, rows, pw)


def main():
    n, top = 12, 25
    for a in sys.argv[1:]:
        if a.startswith("--samples="):
            n = int(a[10:])
        if a.startswith("--top="):
            top = int(a[6:])
    pw = _install()
    surface = pygame.Surface((WIDTH, HEIGHT))
    rows = []
    for fn in (_m6, _m5):
        try:
            fn(surface, n, rows, pw)
        except Exception as e:      # a broken scene must not hide the others
            print("ERROR in %s: %r" % (fn.__name__, e))
            rows.append((9.9, fn.__name__, 0, dict(support=None, arm=9.9, rifle=None)))
    rows.sort(key=lambda r: -r[0])
    shots = {}
    for _w, label, t, rep in rows:
        shots.setdefault(label, []).append((t, rep))
    for label, hits in sorted(shots.items(), key=lambda kv: -len(kv[1]))[:top]:
        t, rep = max(hits, key=lambda h: (h[1]["support"] or 0.0) + h[1]["arm"] + (h[1]["rifle"] or 0.0))
        print("%-34s %2d bad  worst@%5dms support=%s arm=%.3f rifle=%s" % (
            label, len(hits), t,
            "-" if rep["support"] is None else "%.3f" % rep["support"], rep["arm"],
            "-" if rep["rifle"] is None else "%.3f" % rep["rifle"]))
    print("offending shots: %d, samples: %d" % (len(shots), len(rows)))
    if rows:
        print("AE HOLD: FAIL")
        return 1
    print("AE HOLD: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
