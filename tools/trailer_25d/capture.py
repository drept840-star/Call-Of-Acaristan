"""Gameplay clips for the 2.5D announcement trailer (TVA 1 broadcast).

    python tools/trailer_25d/capture.py [act ...] [--seconds N] [--flat]

Acts are the record_fresh_action checkpoints (1 = M1 warehouse, 2 = M2 after
the sniper, 3 = M3 archives). The bot aims through the real 2.5D aim path:
``topdown3d.mouse_world`` returns the point the bot is aiming at, so the
player rig turns where the bullets go. ``--flat`` records with ACA_TD_2D=1
(the "before" footage). Clips land in trailers/announce_25d/clips/.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FLAT = "--flat" in sys.argv
if FLAT:
    os.environ["ACA_TD_2D"] = "1"
sys.path.insert(0, os.path.join(ROOT, "tools"))

import record_fresh_action as r  # noqa: E402
from game import topdown3d as td  # noqa: E402

AIM = [0.0, 0.0, False]
_aim_world = r.Driver.aim_world
_mouse_world = td.mouse_world


def aim_world(self, wx, wy):
    AIM[0], AIM[1], AIM[2] = wx, wy, True
    _aim_world(self, wx, wy)


def mouse_world(h=0.0):
    if AIM[2] and td.active_cam() is not None:
        return AIM[0], AIM[1]
    return _mouse_world(h)


r.Driver.aim_world = aim_world
td.mouse_world = mouse_world


def main():
    args = [a for a in sys.argv[1:] if a != "--flat"]
    seconds = 14.0
    if "--seconds" in args:
        i = args.index("--seconds")
        seconds = float(args[i + 1])
        del args[i:i + 2]
    want = set(args) or {"1", "2", "3"}
    out = os.path.join(ROOT, "trailers", "announce_25d", "clips")
    os.makedirs(out, exist_ok=True)
    r.apply_hud_policy("clean")
    r.SETTINGS.show_crosshair = False
    ff = r.ffmpeg_exe()
    tag = "2d" if FLAT else "3d"
    for act in r._act_table():
        if str(act["n"]) not in want:
            continue
        AIM[2] = False
        a = type("A", (), dict(seed=20261105 + act["n"], seconds=seconds, out_dir=out,
                               crosshair=False, no_ghost_filter=False))()
        rep, err, _total, _drv = r.capture_act(act, a, ff)
        src = os.path.join(out, act["key"] + ".mp4")
        dst = os.path.join(out, "m%d_%s.mp4" % (act["n"], tag))
        os.replace(src, dst)
        os.replace(src[:-4] + ".foley.json", dst[:-4] + ".foley.json")
        print("%s: %s shots, %s kills, err=%r -> %s" % (act["key"], rep["shots"], rep["kills"], err, dst), flush=True)
        r.interactions.clear_radio_queue()


if __name__ == "__main__":
    main()
