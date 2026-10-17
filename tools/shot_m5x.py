"""Polish pass evidence helper: render M5X 3D cutscene frames to PNG.

Usage:
  python tools/shot_m5x.py OUTDIR scene:t_ms [scene:t_ms ...] [--dialogue SPEAKER]
  e.g. python tools/shot_m5x.py shots/polish_pass/08 m5x_vasile_close:1500

Renderer follows ACARISTAN_RENDERER (gl|software). ``--dialogue`` also saves
a cutscene dialogue-box frame for SPEAKER over a dark plate.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
# ACA_POLISH_SRC=<dir> renders from an older source snapshot ("before" shots).
sys.path.insert(0, os.environ.get("ACA_POLISH_SRC", str(ROOT / "src")))

import pygame  # noqa: E402
from core import config  # noqa: E402


def main(argv):
    out = ROOT / argv[0]
    out.mkdir(parents=True, exist_ok=True)
    from cutscenes import m5mid3d
    backend = os.environ.get("ACARISTAN_RENDERER", "auto")
    args = argv[1:]
    while args:
        a = args.pop(0)
        if a == "--dialogue":
            spk = args.pop(0)
            import cutscenes.engine as eng
            config.screen.fill((24, 26, 30))
            eng.reset_dialogue_slide()
            text = ("You came back in that uniform. I hoped you'd at least have the "
                    "decency to look uncomfortable in it.")
            for _ in range(20):
                eng.draw_dialogue_box(config.screen, spk, text, len(text), len(text))
            p = out / ("dialogue_%s.png" % spk.lower())
            pygame.image.save(config.screen, str(p))
            print("saved", p)
            continue
        scene, t = a.rsplit(":", 1)
        surf = pygame.Surface(config.screen.get_size())
        from cutscenes import m5martial3d
        fn = m5mid3d.M5X_SCENES.get(scene) or m5martial3d.M5_3D_SCENES[scene]
        fn(surf, int(t))
        p = out / ("%s_t%s_%s.png" % (scene, t, backend))
        pygame.image.save(surf, str(p))
        print("saved", p)


if __name__ == "__main__":
    main(sys.argv[1:])
