"""M6 3D film + interactive train stills.

    python tools/m6_shots.py [OUT_DIR] [insertion|boxcar|ending|train|all] [--probe]

Renders every authored M6 shot (each shot dict, so both boxcar exit shots and
all four Vasile calls) at a few timestamps into OUT_DIR/<scene>_<n>_<t>.png
plus a contact sheet OUT_DIR/_sheet.jpg, then steps the interactive
TrainScene on its own clock and saves frames across the timeline.  Backend
follows ACARISTAN_RENDERER (auto|gl|software); set ACARISTAN_CUTSCENE3D=0 to
review the fallbacks.

``--probe`` also prints, per frame: head-region luma (mean / p95) of every
face on screen, and for staged sets the deepest body penetration into the
set's registered solids.  Targets: mean 55..170, p95 < 235, penetration
<= 0.02 m.

This is a visual-review tool, not a CI gate.
"""
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

TRAIN_AT = (1.0, 3.0, 7.5, 12.0, 16.7, 18.2, 20.0, 23.5)


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


def _films(surface, out, groups, probe=False):
    shots = [s for g in groups for s in GROUPS[g]]
    rows = len(shots) + (1 if "train" in groups else 0)
    sheet = pygame.Surface((TW * len(FRACS), TH * rows))
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


def _train(surface, out, row, sheet):
    from missions import m6
    from missions.m6 import train3d
    import core.save_system as _save

    try:
        _save.select_slot(0)
    except Exception:
        pass
    m6.start_mission6_train_checkpoint()
    for col, target in enumerate(TRAIN_AT):
        guard = 0
        while train3d.scene().t < target and guard < 4000:
            STATE.dt = 1.0 / 60.0
            train3d.update(None, (WIDTH // 2, HEIGHT // 2))
            STATE.dt = 0.0
            guard += 1
        train3d.draw(surface)
        pygame.image.save(surface, os.path.join(out, "train_%05.2f.png" % target))
        sheet.blit(pygame.transform.smoothscale(surface, (TW, TH)),
                   (col * TW, row * TH))
    if train3d.active():
        train3d.force_finish("tool")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    probe = "--probe" in sys.argv
    out = args[0] if args else os.path.join(ROOT, "shots", "m6")
    which = args[1] if len(args) > 1 else "all"
    groups = list(GROUPS) + ["train"] if which == "all" else [which]
    for g in groups:
        if g not in GROUPS and g != "train":
            print("unknown group %r (use insertion|boxcar|ending|train|all)" % g)
            return 1
    os.makedirs(out, exist_ok=True)
    surface = pygame.Surface((WIDTH, HEIGHT))
    sheet, row = _films(surface, out, [g for g in groups if g in GROUPS], probe)
    if "train" in groups:
        _train(surface, out, row, sheet)
        row += 1
    pygame.image.save(sheet, os.path.join(out, "_sheet.jpg"))
    if m6films._cache.get("failed"):
        print("3D FAILED:", repr(m6films._cache.get("err")))
    print("wrote", out, "(%d rows)" % row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
