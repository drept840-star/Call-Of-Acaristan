"""Interactive 3D character viewer (defaults to andrei_m).

    python tools/view_cast3d.py [cast_key]

Controls:
  Left/Right or drag LMB : rotate
  Up/Down or Mouse Wheel : zoom
  W/S                    : camera height
  P / E                  : cycle pose / expression
  Space                  : toggle auto-spin
  R / Esc                : reset / quit
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402
import engine3d  # noqa: E402
from engine3d import EXPRESSIONS, POSES, box, quad_xz  # noqa: E402
from cutscenes.cast3d import humanoid3d  # noqa: E402

WIN_W, WIN_H = 900, 700
RW, RH = 450, 350
BG = (26, 29, 36)


def main():
    who = sys.argv[1] if len(sys.argv) > 1 else "andrei_m"
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption(f"3D Cast Viewer - {who}")
    clock = pygame.time.Clock()

    font_path = os.path.join(ROOT, "assets", "fonts", "IBMPlexMono-SemiBold.ttf")
    font = pygame.font.Font(font_path, 15) if os.path.exists(font_path) else pygame.font.SysFont(None, 18)

    r = engine3d.Renderer(RW, RH, fog=BG, fog_start=25, fog_end=70)
    r.light = engine3d.Light(direction=(-0.35, 0.72, -0.60), ambient=0.48, diffuse=0.66)
    r.bake(quad_xz(-10, -10, 10, 10, 0.0, (44, 46, 52), seg=4,
                   colfn=lambda i, j: (46, 48, 54) if (i + j) % 2 else (40, 42, 48)))
    r.bake(box(0.8, 0.04, 0.8, (58, 60, 68), center=(0, 0.02, 0)))

    hum = humanoid3d(who)
    poses = list(POSES.keys())
    exprs = list(EXPRESSIONS.keys())
    pi, ei = poses.index("stand"), exprs.index("neutral")

    yaw = 196.0
    pitch = 10.0
    dist = 3.2
    target_y = 0.95
    spinning = False
    dragging = False

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return
                if ev.key == pygame.K_p:
                    pi = (pi + 1) % len(poses)
                elif ev.key == pygame.K_e:
                    ei = (ei + 1) % len(exprs)
                    hum.set_expression(exprs[ei], 0.0)
                elif ev.key == pygame.K_SPACE:
                    spinning = not spinning
                elif ev.key == pygame.K_r:
                    yaw, pitch, dist, target_y = 196.0, 10.0, 3.2, 0.95
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                dragging = True
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                dragging = False
            elif ev.type == pygame.MOUSEMOTION and dragging:
                yaw = (yaw - ev.rel[0] * 0.6) % 360.0
                pitch = max(-25.0, min(55.0, pitch + ev.rel[1] * 0.4))
            elif ev.type == pygame.MOUSEWHEEL:
                dist = max(0.85, min(6.5, dist - ev.y * 0.25))

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            yaw = (yaw - 2.0) % 360.0
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            yaw = (yaw + 2.0) % 360.0
        if keys[pygame.K_UP]:
            dist = max(0.85, dist - 0.06)
        if keys[pygame.K_DOWN]:
            dist = min(6.5, dist + 0.06)
        if keys[pygame.K_w]:
            target_y = min(1.85, target_y + 0.025)
        if keys[pygame.K_s]:
            target_y = max(0.25, target_y - 0.025)
        if spinning and not dragging:
            yaw = (yaw + 0.8) % 360.0

        pr = math.radians(pitch)
        cam = (0.0, target_y + math.sin(pr) * dist, -math.cos(pr) * dist)
        r.set_camera(cam, (0.0, target_y, 0.0), 38)
        r.surface.fill(BG)
        r.begin()
        r.add_static()
        r.add_humanoid(hum, POSES[poses[pi]], (0.0, 0.0, 0.0), yaw, rifle_on=False)
        r.flush(r.surface)

        pygame.transform.scale(r.surface, (WIN_W, WIN_H), screen)
        hud = f"{who} | pose[P]: {poses[pi]} | expr[E]: {exprs[ei]} | drag/arrows/wheel | W/S height | Space spin"
        txt = font.render(hud, True, (230, 232, 236))
        screen.fill((14, 16, 20), (0, WIN_H - 30, WIN_W, 30))
        screen.blit(txt, (12, WIN_H - 24))
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
