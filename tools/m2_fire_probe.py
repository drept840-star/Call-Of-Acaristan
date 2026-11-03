"""Time Mission 2 frames after the tanker blast (fire cost probe).

    python tools/m2_fire_probe.py [--2d] [--live] [--profile]
                                  [--no-fire] [--no-particles] [frames]

Renders post-blast frames in the live path (2.5D unless ACA_TD_2D=1 or
--2d) and prints the median/95th frame time.  ``--live`` runs the real
``game_update`` + ``game_draw`` pair, so particles and fires age the way
they do in play; otherwise only the draw runs and the blast's whole
particle dump stays on screen.  ``--no-fire`` clears the fire zones and the
outer spot fires after the warm-up, ``--no-particles`` the particle list, so
each scene part can be timed on its own.  ``--profile`` prints a cProfile
table of the whole frame.

Visual/perf review tool, not a CI gate.
"""
import cProfile
import os
import pstats
import statistics
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ACA_FREEZE", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()

from core import config as _cfg  # noqa: E402
from core.state import STATE  # noqa: E402


def main():
    args = sys.argv[1:]
    frames = 120
    for a in list(args):
        if a.isdigit():
            frames = int(a)
            args.remove(a)
    if "--2d" in args:
        os.environ["ACA_TD_2D"] = "1"
    live = "--live" in args
    profile = "--profile" in args

    from missions import m2
    from missions.m2 import sniper
    from missions.m2.meta import SAFE_ZONE, STAGE_RUN

    m2.start_mission2_truck(preserve_timer=True)
    STATE.mission2_card = None
    T = _cfg.TILE_SIZE
    STATE.player.rect.center = SAFE_ZONE          # survive the blast
    sniper._explode_tanker()
    STATE.mission2_card = None
    STATE.player.health = 100000                  # stand in the aftermath
    STATE.player.rect.center = (42 * T + T // 2, 48 * T + T // 2)
    fx, fy = STATE.mission2_tanker_rect.center
    STATE.camera_x = fx - _cfg.WIDTH // 2
    STATE.camera_y = fy - _cfg.HEIGHT // 2
    STATE.player_dead = False
    STATE.mission2_tanker_blast_timer = 200
    keys = pygame.key.get_pressed()

    def frame():
        STATE.mission2_stage = STAGE_RUN
        if live:
            m2.game_update(keys)
            STATE.player_dead = False
            STATE.camera_x = fx - _cfg.WIDTH // 2
            STATE.camera_y = fy - _cfg.HEIGHT // 2
        m2.game_draw(STATE.camera_x, STATE.camera_y)

    for _ in range(20):                            # caches, bakes, halo sprites
        frame()
    if "--no-fire" in args:
        STATE.fire_zones[:] = []
        STATE.mission2_tanker_spot_fires = []
    if "--no-particles" in args:
        STATE.particles.clear()
    zones, spots = len(STATE.fire_zones), len(getattr(STATE, "mission2_tanker_spot_fires", ()))

    times = []
    t0 = time.perf_counter()
    if profile:
        pr = cProfile.Profile()
        pr.enable()
    for _ in range(frames):
        t = time.perf_counter()
        frame()
        times.append((time.perf_counter() - t) * 1000.0)
    if profile:
        pr.disable()
        pstats.Stats(pr).sort_stats("tottime").print_stats(22)
    total = (time.perf_counter() - t0) * 1000.0

    # the last half is the settled state in live mode
    tail = sorted(times[len(times) // 2:])
    print("mode: %s  flags: %s" % ("2d" if os.environ.get("ACA_TD_2D") == "1" else "3d",
                                    " ".join(a for a in args if a.startswith("--")) or "-"))
    print("frames: %d  median %.2f ms  p95 %.2f ms  max %.2f ms  (avg %.2f ms)"
          % (frames, statistics.median(times), sorted(times)[int(frames * 0.95) - 1],
             max(times), total / frames))
    print("last-half median %.2f ms" % statistics.median(tail))
    print("fire_zones: %d  spot_fires: %d  particles: %d" % (zones, spots, len(STATE.particles)))


if __name__ == "__main__":
    main()
