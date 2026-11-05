"""The switch shot: one continuous M1 bot run that starts in the flat 2D
view, flips to 2.5D and tilts the camera from straight down to the shipped
64 degree preset.

    python tools/trailer_25d/capture_tilt.py [FLAT_S TILT_S HOLD_S]

``topdown3d.enabled`` reads ACA_TD_2D on every call, so the view is flipped
per frame on one live sim. Writes trailers/announce_25d/clips/m1_tilt.mp4
and m1_tilt.json (the second the 3D view first shows).
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
    flat_s, tilt_s, hold_s = (float(a) for a in (sys.argv[1:4] if len(sys.argv) >= 4 else (4, 3, 4)))
    out_dir = os.path.join(cap.ROOT, "trailers", "announce_25d", "clips")
    os.makedirs(out_dir, exist_ok=True)
    r.apply_hud_policy("clean")
    r.SETTINGS.show_crosshair = False
    act = r._act_table()[0]
    r.random.seed(20261105)
    act["boot"]()
    r.strip_after_boot()
    drv = r.Driver(r.Router(act["tmap"], act["solids"]), crosshair=False, ghost_filter=True)
    out = r.Path(out_dir) / "m1_tilt.mp4"
    tick = r.Ticker(r.ffmpeg_exe(), out)
    cam = td.CAMS["MISSION1"]
    pitch0, dist0 = cam.pitch, cam.dist
    hz = r.SIM_HZ
    total = int((flat_s + tilt_s + hold_s) * hz)
    for n in range(total):
        t = n / float(hz)
        if t < flat_s:
            os.environ["ACA_TD_2D"] = "1"
        else:
            os.environ.pop("ACA_TD_2D", None)
            u = ease((t - flat_s) / tilt_s)
            cam.pitch = 89.5 + (pitch0 - 89.5) * u
            cam.dist = dist0 * (1.06 - 0.06 * u)
        drv.tickno = n
        drv.tick()
        if n % 2 == 1:
            tick.feed()
    print("ffmpeg:", tick.close() or "ok", "->", out)
    with open(str(out)[:-4] + ".json", "w") as fh:
        json.dump({"switch_s": flat_s, "tilt_s": tilt_s, "hold_s": hold_s}, fh)


if __name__ == "__main__":
    main()
