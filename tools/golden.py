"""golden.py - golden-image regression gate for the reworked renderer.

Renders three deterministic Mission 3 stills (ACA_FREEZE=1 pins every
time-driven term: light flicker, mote drift/twinkle) and compares a tiny
grayscale signature against tools/golden.json.

    GOLDEN_UPDATE=1 python tools/golden.py     # re-baseline after art changes
    python tools/golden.py                     # verify
    (smoke_test.py also calls compare() when the baseline exists)

The signature is 40x28 grayscale quantised to 16 levels with a +/-1 level
per-pixel tolerance and a 2% mismatch budget: enough slack for sub-pixel
animation, far too little for a missing shelf, a broken tile or a dead
light pass.
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ["ACA_FREEZE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pygame

from core import config
from core import game_core as gc
from core.state import STATE
from missions import m3

HERE = Path(__file__).resolve().parent
BASE = HERE / "golden.json"
T = config.TILE_SIZE
TOL = 1
BUDGET = 0.02


class EK:
    def __getitem__(self, k):
        return False


def _cam(tx, ty):
    STATE.player.rect.center = (int(tx * T), int(ty * T))
    return m3._clamp_m3_camera(int(tx * T - config.WIDTH // 2),
                               int(ty * T - config.HEIGHT // 2))


def _scene_archives():
    m3.start_mission3_archives_checkpoint(preserve_timer=True)
    return _cam(12, 27)


def _scene_comms():
    from missions.m3 import world as w
    m3.start_mission3_comms_checkpoint(preserve_timer=True)
    return _cam(w._RELAY_TILE_COL - 2, w._RELAY_TILE_ROW - 2)


def _scene_cell():
    gc.start_mission3_breakout_checkpoint(preserve_timer=True)
    cx, cy = m3._interrogation_chair_pos()
    return _cam(cx // T + 3, cy // T + 2)


SCENES = (("archives", _scene_archives), ("comms", _scene_comms),
          ("cell", _scene_cell))


def _sig():
    small = pygame.transform.scale(config.screen, (40, 28))
    arr = pygame.surfarray.array3d(small)
    gray = (arr[:, :, 0].astype(int) + arr[:, :, 1] + arr[:, :, 2]) // 3
    return (gray // 16).ravel().tolist()


def render_all():
    out = {}
    for name, fn in SCENES:
        fcx, fcy = fn()
        config.screen.fill((0, 0, 0))
        gc.game_draw(fcx, fcy)
        gc.game_draw(fcx, fcy)   # second pass: settle per-frame state
        out[name] = _sig()
    return out


def compare(verbose=True):
    if not BASE.exists():
        if verbose:
            print("golden: no baseline at %s (run GOLDEN_UPDATE=1)" % BASE)
        return True
    base = json.loads(BASE.read_text())
    cur = render_all()
    ok = True
    for name, sig in cur.items():
        b = base.get(name)
        if b is None or len(b) != len(sig):
            print("golden: %s missing/mismatched baseline" % name)
            ok = False
            continue
        bad = sum(1 for a, c in zip(b, sig) if abs(a - c) > TOL)
        ratio = bad / len(sig)
        good = ratio <= BUDGET
        ok = ok and good
        if verbose:
            print("golden: %-9s %4d/%d px off  %s" % (
                name, bad, len(sig), "OK" if good else "FAIL"))
    return ok


def main():
    pygame.display.set_mode((config.WIDTH, config.HEIGHT))
    if os.environ.get("GOLDEN_UPDATE") == "1":
        BASE.write_text(json.dumps(render_all()))
        print("golden: baseline written (%d scenes)" % len(SCENES))
        return 0
    return 0 if compare() else 1


if __name__ == "__main__":
    sys.exit(main())

