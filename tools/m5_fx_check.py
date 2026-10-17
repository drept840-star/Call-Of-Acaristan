"""M5 FX checks: reduced motion zeroes handheld/shake/roll; 2D fallback still works.
Usage: python tools/m5_fx_check.py  -> prints M5 FX CHECK: OK / FAIL lines."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import pygame  # noqa: E402

pygame.init()
from core.config import *  # noqa: E402,F401,F403
from core.state import STATE  # noqa: E402
from cutscenes import m5martial3d as m  # noqa: E402
from cutscenes import m5fx3d as fx  # noqa: E402
from cutscenes import m5mid3d as mid  # noqa: E402

ok = True


def check(name, cond):
    global ok
    ok = ok and bool(cond)
    print(("ok   " if cond else "FAIL ") + name)


s = pygame.Surface((WIDTH, HEIGHT))
r, _b = m._rend()
prev = getattr(STATE, "reduced_motion", False)
try:
    STATE.reduced_motion = True
    check("handheld zero under reduced motion", fx.handheld(1234, 0.02) == (0.0, 0.0, 0.0))
    check("shake zero under reduced motion", fx.shake(600, 520, 900, 0.07) == (0.0, 0.0, 0.0, 0))
    m._river(s, 5000)               # shot B: handheld + roll
    eye_rm = r.cam
    px = fx.set_cam(r, 600, (0, 1.6, -3), (0, 1.5, 0), 45, hh=0.02, roll=1.0,
                    shk=fx.shake(600, 520, 900, 0.07))
    check("no roll/px offset under reduced motion", px == 0 and abs(r.up[0]) < 1e-9)
    STATE.reduced_motion = False
    check("handheld active normally", fx.handheld(1234, 0.02) != (0.0, 0.0, 0.0))
    check("shake active normally", fx.shake(600, 520, 900, 0.07)[0] != 0.0)
    m._river(s, 5000)
    check("camera differs only by the drift (< 5 cm)",
          0 < sum((a - b) ** 2 for a, b in zip(r.cam, eye_rm)) ** 0.5 < 0.05)
finally:
    STATE.reduced_motion = prev

os.environ["ACARISTAN_CUTSCENE3D"] = "0"
check("ACARISTAN_CUTSCENE3D=0 -> 2D path", m.draw_m5_scene_3d("m5_river_gate", s, 1000) is False)
os.environ["ACARISTAN_CUTSCENE3D"] = "1"
check("3D path draws", m.draw_m5_scene_3d("m5_river_gate", s, 1000) is True)
orig = fx.rain3d


def _boom(*a, **k):
    raise RuntimeError("forced")


fx.rain3d = _boom
try:
    res = m.draw_m5_scene_3d("m5_river_gate", s, 1000)
    check("forced 3D exception -> False + failed flag", res is False and m._cache["failed"])
    check("m5x still draws (2D fallback)", mid.draw_m5x("m5x_breach", s, 800) is True)
finally:
    fx.rain3d = orig
    m._cache["failed"], m._cache["err"] = False, None
print("M5 FX CHECK: " + ("OK" if ok else "FAIL"))
