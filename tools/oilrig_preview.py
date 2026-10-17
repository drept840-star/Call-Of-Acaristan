"""Off-screen preview of the oil-rig strike cinematic (missions.walking_attack3d).

Simulates the walking_sim attack timeline faithfully (boat motion, missile
launches, rig status flips, screen shake) and dumps PNG frames so the scene
can be reviewed without playing the game.

Usage:
    python tools/oilrig_preview.py [out_dir] [frame ...]
Default frames are key story beats; pass explicit frame numbers to override.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

from core.config import WIDTH, HEIGHT  # noqa: E402
from missions.walking_attack3d import draw_oilrig_attack_3d  # noqa: E402

# Mirror of walking_sim.py ATK_* constants (frames @60fps).
ATK_BOAT_APPEAR = 90
ATK_TARGET_CENTER, ATK_MISSILE_1_LAUNCH, ATK_IMPACT_CENTER = 850, 910, 990
ATK_TARGET_LEFT, ATK_MISSILE_2_LAUNCH, ATK_IMPACT_LEFT = 1270, 1330, 1410
ATK_TARGET_RIGHT, ATK_MISSILE_3_LAUNCH, ATK_IMPACT_RIGHT = 1710, 1770, 1850
ATK_FISHERMAN_3, ATK_FISHERMAN_4 = 2320, 2800
IMPACT_FRAMES = (ATK_IMPACT_LEFT, ATK_IMPACT_CENTER, ATK_IMPACT_RIGHT)
SHOT_FRAMES = (ATK_TARGET_CENTER, ATK_TARGET_LEFT, ATK_TARGET_RIGHT, ATK_FISHERMAN_3)

STRIKES = (
    (1, ATK_TARGET_CENTER, ATK_MISSILE_1_LAUNCH, ATK_IMPACT_CENTER),
    (0, ATK_TARGET_LEFT, ATK_MISSILE_2_LAUNCH, ATK_IMPACT_LEFT),
    (2, ATK_TARGET_RIGHT, ATK_MISSILE_3_LAUNCH, ATK_IMPACT_RIGHT),
)


class FakeState:
    def __init__(self):
        self.walk_attack_timer = 0
        self.walk_boat_active = False
        self.walk_boat_x = 0.0
        self.walk_boat_y = 0.0
        self.walk_missiles = []
        self.walk_explosions = []
        self.rig_status = ["ONLINE", "ONLINE", "ONLINE"]
        self.screen_shake = 0
        self.reduced_motion = False


def step(state, t):
    """Advance the fake state to frame t, mirroring _update_walk_attack_timeline."""
    state.walk_attack_timer = t
    if t >= ATK_BOAT_APPEAR and not state.walk_boat_active:
        state.walk_boat_active = True
        state.walk_boat_x = 0.0
    for idx, target, launch, impact in STRIKES:
        if t >= target and state.rig_status[idx] == "ONLINE":
            state.rig_status[idx] = "TARGETED"
        if t >= launch and not any(m["rig_index"] == idx for m in state.walk_missiles) \
                and state.rig_status[idx] != "DESTROYED" and t < impact:
            state.walk_missiles.append({
                "start_x": float(state.walk_boat_x + 50),
                "t": 0.0,
                "speed": 1.0 / max(1, impact - launch),
                "rig_index": idx,
            })
        if t >= impact and state.rig_status[idx] != "DESTROYED":
            state.rig_status[idx] = "DESTROYED"
            state.screen_shake = max(state.screen_shake, 34 + idx * 3)
    for idx, impact in enumerate(IMPACT_FRAMES):
        if t >= impact + 36 and state.rig_status[idx] == "DESTROYED":
            state.screen_shake = max(state.screen_shake, 22 - idx * 2)
    if state.walk_boat_active:
        if t < ATK_TARGET_CENTER:
            speed = 0.32
        elif t < ATK_IMPACT_RIGHT + 120:
            speed = 0.60
        elif t < ATK_FISHERMAN_4:
            speed = 0.78
        else:
            speed = 1.55
        state.walk_boat_x += speed
    for m in state.walk_missiles[:]:
        m["t"] = min(1.0, m["t"] + m["speed"])
        if m["t"] >= 1.0:
            state.walk_missiles.remove(m)


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].isdigit() else \
        os.path.join(ROOT, "tools", "out", "oilrig")
    frames = [int(a) for a in sys.argv[1:] if a.isdigit()] or [
        30, 200, 700, 905, 950, 992, 1100, 1380, 1430, 1800, 1900, 2400, 3000,
    ]
    os.makedirs(out_dir, exist_ok=True)
    pygame.init()
    surface = pygame.Surface((WIDTH, HEIGHT))
    state = FakeState()
    wanted = sorted(frames)
    target = wanted[0]
    for t in range(0, max(wanted) + 1):
        step(state, t)
        if t == target:
            draw_oilrig_attack_3d(surface, state, IMPACT_FRAMES, shot_frames=SHOT_FRAMES)
            path = os.path.join(out_dir, "frame_%04d.png" % t)
            pygame.image.save(surface, path)
            print("wrote", path)
            wanted.pop(0)
            if not wanted:
                break
            target = wanted[0]
    print("done")


if __name__ == "__main__":
    main()
