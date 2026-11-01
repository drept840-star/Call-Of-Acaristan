"""walk_probe.py - framed shots + draw-cost probe for the walking sim.

    python tools/walk_probe.py                 # every scene -> shots/walk/<scene>.png
    python tools/walk_probe.py --tag after     # shots/walk/<scene>.after.png
    python tools/walk_probe.py --only van,harbor --frames 120 --no-shots

Renders off-screen with the dummy video driver and ACA_FREEZE=1, so the two
runs of a before/after pair see the same pinned clock (rain, lamp flicker,
exhaust puff). Times ``ws.draw_walking_sim`` over N frames: the number is CPU
draw cost (ms/frame -> fps ceiling), not vsynced fps.
"""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ["ACA_FREEZE"] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pygame  # noqa: E402

from core import config  # noqa: E402
from core.state import STATE  # noqa: E402
from missions import walking_sim as ws  # noqa: E402

T = config.TILE_SIZE
OUT = ROOT / "shots" / "walk"


class _NoKeys:
    def __getitem__(self, _k):
        return False


def _look(tx, ty, cam=None):
    """Put the player on tile (tx, ty) and the camera on cam or the player."""
    ws.walk_player.rect.center = (int(tx * T), int(ty * T))
    cx, cy = cam if cam else (tx * T, ty * T)
    ws.walk_camera_x = cx - config.WIDTH // 2
    ws.walk_camera_y = cy - config.HEIGHT // 2
    ws._clamp_walk_camera()
    ws._walk_update_render()


def _fresh():
    ws.start_walking_sim()
    STATE.dt = 1.0 / 60.0


def scene_start():
    """Spawn alley: poster, flak-jacket stash, first lamp."""
    _fresh()
    _look(4, 3)


def scene_alley():
    """Container maze with the laundry line and the unreliable lamp."""
    _fresh()
    _look(13, 6)


def scene_checkpoint():
    """KRAP checkpoint story point + the hungry kid."""
    _fresh()
    _look(18, 4)


def scene_market():
    """Fish market, old woman, ammo crate."""
    _fresh()
    _look(26, 6)


def scene_harbor():
    """Overlook railing, fisherman, the water side of the slum."""
    _fresh()
    _look(40, 6)


def scene_van():
    """The KRAP extraction van, post-firefight."""
    _fresh()
    ws.walk_firefight_triggered = True
    ws.walk_after_firefight = True
    STATE.walk_after_firefight = True
    _look(44, 6)


def scene_dark():
    """A lamp-lit stretch with no player torch nearby: reads the light pass."""
    _fresh()
    _look(31, 5)


SCENES = (
    ("start", scene_start),
    ("alley", scene_alley),
    ("checkpoint", scene_checkpoint),
    ("market", scene_market),
    ("harbor", scene_harbor),
    ("van", scene_van),
    ("dark", scene_dark),
)


def main():
    argv = sys.argv[1:]
    tag = argv[argv.index("--tag") + 1] if "--tag" in argv else ""
    frames = int(argv[argv.index("--frames") + 1]) if "--frames" in argv else 60
    shots = "--no-shots" not in argv
    only = None
    if "--only" in argv:
        only = set(argv[argv.index("--only") + 1].split(","))
    if shots:
        OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for name, fn in SCENES:
        if only and name not in only:
            continue
        fn()
        if shots:
            for _ in range(2):                       # settle caches + camera
                ws.update_walking_sim(_NoKeys())
                ws.draw_walking_sim()
            path = OUT / ("%s.%s.png" % (name, tag) if tag else "%s.png" % name)
            pygame.image.save(config.screen, str(path))
        t0 = time.perf_counter()
        for _ in range(frames):
            ws.update_walking_sim(_NoKeys())
            ws.draw_walking_sim()
        ms = (time.perf_counter() - t0) * 1000.0 / frames
        res[name] = round(ms, 2)
        print("%-11s %6.2f ms/frame  (%5.0f fps ceiling)" % (name, ms, 1000.0 / max(ms, 1e-6)))
    print("WALK PROBE: OK (%d scenes%s)" % (len(res), ", tag=%s" % tag if tag else ""))


if __name__ == "__main__":
    main()
