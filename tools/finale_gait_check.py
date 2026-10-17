"""M5 finale gait check: Maru timing, footstep contact times, world foot drift.

    python tools/finale_gait_check.py
"""
import os, sys, math
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
from cutscenes import m5shadow3d as m5


def main():
    b, u, m = m5.actors()
    print(f"route {m5._CUM[-1]:.2f} m  stop {m5.MARU_STOP:.2f}  stride {m5.MARU_STRIDE:.3f}"
          f"  t_stop {m5.MARU_T_STOP:.2f}  t_go {m5.MARU_T_GO:.2f}  t_in {m5.MARU_T_IN:.2f}"
          f"  door_open {m5.DOOR_OPEN}  shut {m5.DOOR_SHUT}  gone {m5.MARU_GONE:.2f}  scale {m._scale:.3f}")
    # world foot positions: foot slot origin = ankle (slots 9 / 15)
    prev = None; contacts = []; drift = {"l": [], "r": []}; planted = {"l": None, "r": None}
    for i in range(0, int(m5.MARU_GONE * 1000), 10):
        pose, pos, yaw = m5.maru_pose(m, i)
        places, j, root = m.pose_world(pose, pos, yaw, False)
        feet = {}
        for side, slot in (("l", 9), ("r", 15)):
            M, org = next((M, o) for s, key, M, o, g, fb in places if s == slot)
            feet[side] = (org[0] + root[0] - pos[0] + pos[0], org[1] + root[1], org[2] + root[2])
        if prev:
            for side in "lr":
                low = feet[side][1] - min(feet["l"][1], feet["r"][1]) < .012
                if low and planted[side] is None:
                    planted[side] = feet[side]; contacts.append((i, side))
                elif low:
                    p0 = planted[side]
                    drift[side].append(math.hypot(feet[side][0] - p0[0], feet[side][2] - p0[2]))
                elif not low:
                    planted[side] = None
        prev = feet
    print("contacts ms:", " ".join(f"{t}{s}" for t, s in contacts))
    for side in "lr":
        d = drift[side]
        print(side, "max stance drift cm: %.2f" % (100 * max(d) if d else 0))


if __name__ == "__main__":
    main()
