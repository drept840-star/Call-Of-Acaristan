"""The switch shot, recorded twice per tick: one M3 bot run drawn in the flat
2D view and in 2.5D on the same sim frame, so the trailer can sweep a depth
wave across the map with both pictures in register.

    python tools/trailer_25d/capture_wave.py [ACT FLAT_S TILT_S HOLD_S]

The 2.5D camera holds straight down (matching the 2D framing) for FLAT_S,
then tilts to the shipped preset over TILT_S and holds. Writes
trailers/announce_25d/clips/wave_2d.mp4, wave_3d.mp4 and wave.json.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import capture as cap  # noqa: E402  (patches the bot's 2.5D aim)

r = cap.r
td = cap.td


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def main():
    a = sys.argv[1:5] if len(sys.argv) >= 5 else ("3", 5.6, 3.0, 4.0)
    act_n, (flat_s, tilt_s, hold_s) = int(a[0]), (float(x) for x in a[1:4])
    out_dir = os.path.join(cap.ROOT, "trailers", "announce_25d", "clips")
    os.makedirs(out_dir, exist_ok=True)
    r.apply_hud_policy("clean")
    r.SETTINGS.show_crosshair = False
    act = [x for x in r._act_table() if x["n"] == act_n][0]
    r.random.seed(20261105 + act_n)
    act["boot"]()
    r.strip_after_boot()
    drv = r.Driver(r.Router(act["tmap"], act["solids"]), crosshair=False, ghost_filter=True)
    t3 = r.Ticker(r.ffmpeg_exe(), r.Path(out_dir) / "wave_3d.mp4")
    t2 = r.Ticker(r.ffmpeg_exe(), r.Path(out_dir) / "wave_2d.mp4")
    cam = td.CAMS["MISSION%d" % act_n]
    pitch0, dist0 = cam.pitch, cam.dist
    hz = r.SIM_HZ
    total = int((flat_s + tilt_s + hold_s) * hz)
    for n in range(total):
        t = n / float(hz)
        u = ease((t - flat_s) / tilt_s)
        cam.pitch = 89.5 + (pitch0 - 89.5) * u
        cam.dist = dist0 * (1.06 - 0.06 * u)
        os.environ.pop("ACA_TD_2D", None)
        drv.tickno = n
        drv.tick()
        if n % 2 == 1:
            t3.feed()
            os.environ["ACA_TD_2D"] = "1"
            r.gc.game_draw(drv.cam[0], drv.cam[1])
            os.environ.pop("ACA_TD_2D", None)
            t2.feed()
    print("ffmpeg:", t3.close() or "ok", t2.close() or "ok")
    with open(os.path.join(out_dir, "wave.json"), "w") as fh:
        json.dump({"act": act_n, "flat_s": flat_s, "tilt_s": tilt_s, "hold_s": hold_s}, fh)


if __name__ == "__main__":
    main()
