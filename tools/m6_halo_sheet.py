"""B8 tuning sheet: one M6 sodium lamp at 5/15/40/80 m, four depth cases.

Each case shows the pre-redesign look (flat bands, 28 px cap, drawn after the
frame with no depth test - the old GL path) next to the shipped m6fx3d halo
composited by GLRenderer (world-depth masked, anchor-gated).  Run with the
GPU backend:

    python tools/m6_halo_sheet.py [--software]

Saves ``shots/_m6_halo/sheet.png``.  Dev tool only; never shipped.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
if "--software" in sys.argv:
    os.environ["ACARISTAN_RENDERER"] = "software"
else:
    os.environ["ACARISTAN_RENDERER"] = "gl"

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((64, 64))

from engine3d import Renderer  # noqa: E402
from engine3d.core import Mesh, box, quad_xz  # noqa: E402
from cutscenes import m6fx3d as fx  # noqa: E402

CELL_W, CELL_H = 320, 160
DISTS = (5.0, 15.0, 40.0, 80.0)
CASES = ("sky", "wall behind", "pole", "behind wall")
SKY = (5, 7, 12)


def _legacy_draw(surface, sx, sy, scale):
    """The 2a3be34 halo: 28 px cap, three flat bands, a hot core."""
    rad = min(28, 2.2 * scale)
    if rad < 1.5:
        return
    for edge, level in ((1.0, 0.08), (0.64, 0.20), (0.34, 0.42)):
        r = max(1, int(rad * edge))
        img = pygame.Surface((r * 2 + 2, r * 2 + 2))
        img.fill((0, 0, 0))
        pygame.draw.circle(
            img, tuple(int(v * level) for v in (255, 181, 79)),
            (r + 1, r + 1), r)
        surface.blit(img, (int(sx - r), int(sy - r)),
                     special_flags=pygame.BLEND_ADD)
    pygame.draw.circle(surface, (255, 251, 206), (int(sx), int(sy)),
                       max(1, int(rad * 0.2)))


def _add_world(r, lamp_z, case):
    def add(m):
        r.add_dynamic(m.verts, [(f[0], f[1], f[2], f[3], None, f[4])
                                for f in m.faces])
    ground = Mesh()
    ground.add(quad_xz(-50, -50, 50, 50, 0.0, (30, 34, 42), seg=4))
    add(ground)
    if case in ("wall behind", "pole"):
        w = Mesh()
        w.add(box(14, 7, 0.35, (46, 48, 56), center=(0, 3.5, lamp_z + 2.2)))
        add(w)
    if case == "pole":
        p = Mesh()
        p.add(box(0.22, 5.0, 0.22, (24, 26, 32), center=(0.22, 2.5, lamp_z - 1.0)))
        add(p)
    if case == "behind wall":
        w = Mesh()
        w.add(box(14, 7, 0.35, (46, 48, 56), center=(0, 3.5, lamp_z - 1.0)))
        add(w)


def render_cell(r, dist, case, legacy=False):
    buf = pygame.Surface((CELL_W, CELL_H))
    buf.fill(SKY)
    lamp_z = -6.0 + dist
    r.set_camera((0.0, 1.9, -6.0), (0.0, 2.2, 10.0), 55.0)
    r.begin()
    _add_world(r, lamp_z, case)
    lamp = (0.0, 2.6, lamp_z)
    fn = fx.sodium_lamp(0, seed=3, radius_m=2.2, intensity=0.9)
    if not legacy:
        r.add_sprite(lamp, fn, layer=fx.FX_LAYER)
    p = r.project(lamp)
    r.flush(buf)
    if legacy and p is not None:
        _legacy_draw(buf, p[0], p[1], p[2])
    return buf


def main():
    r = Renderer(CELL_W, CELL_H, fog=(9, 11, 16), fog_start=30.0, fog_end=220.0)
    cols = len(DISTS) * 2
    out = pygame.Surface((CELL_W * cols, CELL_H * len(CASES)))
    out.fill((0, 0, 0))
    font = pygame.font.SysFont("Consolas", 12, bold=True)
    for row, case in enumerate(CASES):
        for ci, dist in enumerate(DISTS):
            for si, legacy in enumerate((True, False)):
                cell = render_cell(r, dist, case, legacy)
                x = (ci * 2 + si) * CELL_W
                y = row * CELL_H
                out.blit(cell, (x, y))
                lab = font.render("%s // %gm // %s" % (
                    case, dist, "OLD" if legacy else "NEW"), True,
                    (150, 160, 170) if legacy else (220, 232, 240))
                out.blit(lab, (x + 6, y + 4))
    os.makedirs(os.path.join(ROOT, "shots", "_m6_halo"), exist_ok=True)
    path = os.path.join(ROOT, "shots", "_m6_halo", "sheet.png")
    pygame.image.save(out, path)
    print("M6 HALO SHEET:", path)


if __name__ == "__main__":
    main()
