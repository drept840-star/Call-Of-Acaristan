"""Render stills of the walking-sim first-person reward cutscenes.

Usage: python tools/walk_fp_shots.py [--out shots/walk_fp] [--scene kid|crate]
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import tempfile

_TMP = Path(tempfile.mkdtemp(prefix="acaristan_walkshots_"))
from core import profile_store, save_system, settings_store  # noqa: E402

save_system.SAVE_FILE = str(_TMP / "save_data.json")
settings_store.SAVE_FILE = str(_TMP / "settings.json")
profile_store.PROFILE_FILE = str(_TMP / "profile.json")

import pygame  # noqa: E402

import core.config as config  # noqa: E402
import core.game_core as gc  # noqa: E402
from core import artpack  # noqa: E402
import missions.walking_sim as ws  # noqa: E402


def _shot(name, out):
    pygame.image.save(config.screen, str(out / f"{name}.png"))


def main():
    args = sys.argv[1:]
    out = ROOT / "shots" / "walk_fp"
    if "--out" in args:
        out = Path(args[args.index("--out") + 1])
    out.mkdir(parents=True, exist_ok=True)

    gc.start_walking_sim()
    w = ws
    kid = w.walk_npcs[0]

    plan = {
        "kid_kevlar": [0, 20, 40, 70, 110, 150, 190, 240, 280, 310, 330,
                       352, 375, 400, 450, 490, 515],
        "crate_ammo": [0, 15, 40, 70, 100, 120, 140, 165, 195],
        "crate_kevlar": [0, 15, 40, 70, 100, 120, 140, 165, 205],
    }
    for scene, frames in plan.items():
        if scene == "kid_kevlar":
            w._start_walk_fp_cutscene(scene, scene, npc=kid)
        elif scene == "crate_ammo":
            w._start_walk_fp_cutscene(scene, "stash_ammo", stash=w.walk_stashes[0])
        else:
            w._start_walk_fp_cutscene(scene, "stash_kevlar", stash=w.walk_stashes[1])
        for t in frames:
            w.walk_fp_cutscene["timer"] = t
            config.screen.fill((0, 0, 0))
            w._draw_walk_fp_cutscene(config.screen)
            _shot(f"{scene}_t{t:03d}", out)
        w.walk_fp_cutscene = None

    # The real in-game composite: gameplay draw + cutscene overlay + letterbox.
    w._start_walk_fp_cutscene("kid_kevlar", "kid_kevlar", npc=kid)
    for t in (200, 420):
        w.walk_fp_cutscene["timer"] = t
        config.screen.fill((0, 0, 0))
        w.draw_walking_sim()
        _shot(f"ingame_kid_t{t}", out)
    w.walk_fp_cutscene = None

    print("WALK FP SHOTS: OK", out)


if __name__ == "__main__":
    main()
