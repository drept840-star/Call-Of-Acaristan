"""3D cast line-up: python tools/cast_lineup.py [body|face] [out.jpg] [key ...]

Renders every figure_kit cast member through the same 3D rig the cutscenes use
(m5martial3d._hum, so M5 overrides like Vasile's are included), one tile each,
labelled, into tools/m5_r2_shots/<out>. Prints the JPEG as base64 between
B64START/B64END markers for remote review.
"""
import base64
import io
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ACARISTAN_RENDERER", "software")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()
from core.config import *  # noqa: E402,F401,F403
from cutscenes import m5martial3d as m3d  # noqa: E402
from cutscenes.cast3d import CAST3D_ALIASES  # noqa: E402
from cutscenes.figure_kit import SPECS  # noqa: E402

OUT = os.path.join(ROOT, "tools", "m5_r2_shots")
NAMES = {v: k for k, v in CAST3D_ALIASES.items()}


def render(key, mode, tw, th):
    from engine3d.core import Light, quad_xz
    r, buf = m3d._rend(tw, th)
    if mode == "face":
        # aim at each character's own head height (scale = height/258)
        sk = CAST3D_ALIASES.get(key, key)
        hy = 1.66 * SPECS.get(sk, {}).get("height", 258) / 258.0
        cam, tgt, fov = (0.0, hy + 0.02, -1.15), (0.0, hy, 0.0), 26
    else:
        cam, tgt, fov = (0.0, 1.05, -4.6), (0.0, 0.95, 0.0), 32
    r.set_camera(cam, tgt, fov)
    r.fog, r.fog_start, r.fog_end = (30, 32, 38), 30.0, 60.0
    r.light = Light(direction=(-0.4, 0.8, -0.6), ambient=0.5, diffuse=0.7, tint=(1.05, 1.0, 0.95))
    buf.blit(m3d._sky(tw, th, (58, 62, 72), (28, 30, 36)), (0, 0))
    r.begin()
    m3d._add(r, quad_xz(-3, -3, 3, 3, 0.0, (44, 44, 48), seg=2))
    hum = m3d._hum(key)
    r.add_humanoid(hum, dict(spine=0), (0.0, 0, 0.0), m3d._yaw_to((0, 0, 0), (0, 0, -5)),
                   rifle_on=False)
    r.flush(buf)
    return buf.copy()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "body"
    out = sys.argv[2] if len(sys.argv) > 2 else "cast_" + mode + ".jpg"
    keys = sys.argv[3:] or (list(SPECS.keys()) + ["anchor"])
    tw = int(os.environ.get("CAST_TW", "200"))
    th = tw * 3 // 2 if mode == "body" else tw
    cols = int(os.environ.get("CAST_COLS", "6"))
    rows = (len(keys) + cols - 1) // cols
    lab = 22
    sheet = pygame.Surface((tw * cols, (th + lab) * rows))
    sheet.fill((16, 16, 20))
    font = pygame.font.SysFont("arial", 15, bold=True)
    for i, k in enumerate(keys):
        x, y = (i % cols) * tw, (i // cols) * (th + lab)
        try:
            sheet.blit(render(k, mode, tw, th), (x, y))
        except Exception as e:  # keep going: one bad spec must not hide the rest
            print("FAIL", k, repr(e))
        name = k + (" (" + NAMES[k] + ")" if k in NAMES else "")
        t = font.render(name, True, (235, 225, 200))
        sheet.blit(t, (x + (tw - t.get_width()) // 2, y + th + 3))
        pygame.draw.rect(sheet, (60, 60, 66), (x, y, tw, th + lab), 1)
    print("KEYS", " ".join(keys))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, out)
    from PIL import Image  # lazy: tools only
    img = Image.frombytes("RGB", sheet.get_size(), pygame.image.tobytes(sheet, "RGB"))
    q = int(os.environ.get("CAST_Q", "55"))
    img.save(path, quality=q)
    with open(path, "rb") as f:
        data = f.read()
    if os.environ.get("CAST_B64", "1") == "1":
        print("B64START" + base64.b64encode(data).decode() + "B64END")
    print("BYTES", len(data))


if __name__ == "__main__":
    main()
