"""M5 gauntlet: render every Mission 5 surface we review (top-down stages,
sprite close-ups, every 3D cutscene take + 2D fallbacks) into tools/m5_r2_shots/g_*.png.

    python tools/m5_gauntlet_shots.py [td] [cut] [mart] [c2d]
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ACARISTAN_RENDERER", "software")
os.environ["ACARISTAN_CUTSCENE3D"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()
from core.config import *  # noqa: E402,F401,F403
from core.state import STATE  # noqa: E402

OUT = os.path.join(ROOT, "tools", "m5_r2_shots")
os.makedirs(OUT, exist_ok=True)
WHAT = set(sys.argv[1:]) or {"td", "cut", "mart"}
T = TILE_SIZE


def save(name):
    pygame.image.save(screen, os.path.join(OUT, "g_" + name + ".png"))
    print("shot", name)


def topdown():
    import missions.m5 as m5
    from missions.m5 import flow, draw, quarter, world

    m5.start_m5()

    def shot(name, wx, wy, frames=3):
        STATE.player.rect.center = (int(wx), int(wy))
        cx, cy = wx - WIDTH // 2, wy - HEIGHT // 2
        for _ in range(frames):
            draw.game_draw(cx, cy)
        save(name)

    flow._enter_hq()
    shot("hq_west", 4 * T, 11 * T)
    shot("hq_east", 20 * T, 8 * T)
    shot("hq_office", 24 * T, 5 * T)
    flow._start_vasile_dialogue()
    flow._m5_dlg["char_idx"] = 9999
    shot("dialogue", 24 * T, 5 * T)
    flow._dlg_reset()
    STATE.m5_dialogue_active = False
    flow._enter_quarter()
    shot("quarter_start", 6 * T, 15 * T)
    for i in range(300):
        STATE.player.rect.center = (int((6 + i * 0.06) * T), 15 * T)
        quarter.update()
    shot("quarter_mid", 22 * T, 15 * T)
    shot("quarter_east", 33 * T, 15 * T)
    flow._enter_printworks()
    px, py = STATE.player.rect.center
    shot("print_entry", px, py)
    mp = world._maru_office_pos()
    shot("print_maru", mp[0] - 40, mp[1] + 20)
    try:
        flow._begin_raid()
        for _ in range(90):
            try:
                from missions.m5 import systems
                systems.game_update(pygame.key.get_pressed())
            except Exception as e:  # noqa: BLE001
                print("raid tick err", e)
                break
        shot("print_raid", mp[0] - 40, mp[1] + 60)
    except Exception as e:  # noqa: BLE001
        print("raid err", e)
    try:
        flow._enter_tunnel()
        px, py = STATE.player.rect.center
        shot("tunnel", px + 120, py)
    except Exception as e:  # noqa: BLE001
        print("tunnel err", e)


def cuts():
    from cutscenes import m5mid3d
    from missions.m5.meta import M5_MID_CUTSCENES
    ms = {s["scene"]: s.get("min_ms", 3000) for v in M5_MID_CUTSCENES.values() for s in v}
    for name, fn in m5mid3d.M5X_SCENES.items():
        t = int(ms.get(name, 3000) * 0.6)
        fn(screen, t)
        save("c3_" + name[4:])
        if "c2d" in WHAT:
            m5mid3d.draw_m5x_2d(name, screen, t)
            save("c2_" + name[4:])


def martial():
    from cutscenes import m5martial3d as m3
    from missions.m5 import meta
    shots = []
    for v in vars(meta).values():
        if isinstance(v, list):
            shots += [s for s in v if isinstance(s, dict) and str(s.get("scene", "")).startswith("m5_")]
    seen = {}
    for s in shots:
        seen.setdefault(s["scene"], s.get("min_ms", 3000))
    for name, ms in seen.items():
        t = int(ms * 0.6)
        ok = m3.draw_m5_scene_3d(name, screen, t)
        save("m3_" + name[3:])
        if not ok:
            print("3D FAILED", name, m3._cache.get("err"))


if "td" in WHAT:
    topdown()
if "cut" in WHAT:
    cuts()
if "mart" in WHAT:
    martial()
print("GAUNTLET SHOTS OK")
