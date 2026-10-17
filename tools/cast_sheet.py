"""Cast sheets: the 2D cutscene figures (figure_kit) beside their 3D rigs.

    python tools/cast_sheet.py
      -> outputs/cast/cast_lineup.png    3D line-up (engine3d)
      -> outputs/cast/cast_compare.png   2D vs 3D, full body + heads
      -> outputs/cast/<name>.png         3D portrait per character

3D looks are NOT authored here: cutscenes.cast3d.spec3d() derives them from
cutscenes.figure_kit.SPECS, so editing a 2D spec updates both renders.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

# (display name, figure_kit key, role, 3D pose, 3D overrides)
CAST = [
    ("BIRIBEL", "biribel", "KRAP operator", "stand", {}),
    ("VASILE", "vasile", "KRAP commander", "stand", {}),
    ("MARU", "maru", "MAG", "stand", {}),
    ("BODI", "bodi", "Farmer", "stand", {}),
    ("ALEX", "alex", "MAG runner", "stand", {}),
    ("UCILEV", "ucilev", "Presidential Guard", "stand", {}),
    ("VOLKOV", "volkov", "IPA logistics clerk", "stand", {}),
    ("RETARDOVICI", "president", "President of Acaristan", "stand", {}),
]
BG = (30, 32, 38)
INK, DIM, ORANGE = (238, 233, 223), (154, 160, 168), (255, 122, 26)


def _stage(r):
    from engine3d import quad_xz, box
    r.bake(quad_xz(-14, -6, 14, 14, 0.0, (46, 48, 54), seg=2,
                   colfn=lambda i, j: (46, 48, 54) if (i + j) % 2 else (42, 44, 50)))
    r.bake(box(30, 8, 0.4, (30, 32, 38), center=(0, 4, 3.2)))


def _render3d(hum, w, h, cam, look, fov, light, yaw=196.0, pose="stand"):
    import engine3d
    from engine3d import POSES
    r = engine3d.Renderer(w, h, fog=BG, fog_start=30, fog_end=80)
    r.light = light
    _stage(r)
    r.set_camera(cam, look, fov)
    r.surface.fill(BG)
    r.begin(); r.add_static()
    r.add_humanoid(hum, POSES[pose], (0, 0, 0), yaw, rifle_on=False)
    r.flush(r.surface)
    return r


def render():
    pygame.init()
    pygame.display.set_mode((64, 64))
    import engine3d
    from engine3d import POSES
    from cutscenes import figure_kit as fk
    from cutscenes.cast3d import humanoid3d
    font_dir = os.path.join(ROOT, "assets", "fonts")
    f_name = pygame.font.Font(os.path.join(font_dir, "Oswald.ttf"), 30)
    f_role = pygame.font.Font(os.path.join(font_dir, "IBMPlexMono-SemiBold.ttf"), 14)
    f_title = pygame.font.Font(os.path.join(font_dir, "Oswald.ttf"), 54)
    out_dir = os.path.join(ROOT, "outputs", "cast")
    os.makedirs(out_dir, exist_ok=True)
    light = engine3d.Light(direction=(-0.35, 0.7, -0.6), ambient=0.46, diffuse=0.66)
    actors = {key: humanoid3d(key, **ov) for _n, key, _r, _p, ov in CAST}

    # ── 3D line-up ──
    W, H = 640, 300
    r = engine3d.Renderer(W, H, fog=BG, fog_start=30, fog_end=80)
    r.light = light
    _stage(r)
    r.set_camera((0, 1.3, -9.4), (0, 0.95, 0), 44)
    r.surface.fill(BG)
    r.begin(); r.add_static()
    xs = [(-2.75 + i * 1.1) for i in range(len(CAST))]
    for x, (_n, key, _r, pose, _o) in zip(xs, CAST):
        r.add_humanoid(actors[key], POSES[pose], (x, 0, 0), 180.0 + (x * -4), rifle_on=False)
    r.flush(r.surface)
    S = 2
    sheet = pygame.Surface((W * S, H * S + 190))
    sheet.fill((21, 24, 30))
    sheet.blit(pygame.transform.scale(r.surface, (W * S, H * S)), (0, 90))
    t = f_title.render("CALL OF ACARISTAN  -  CAST", True, INK)
    sheet.blit(t, (40, 16))
    pygame.draw.rect(sheet, ORANGE, (40, 82, t.get_width(), 5))
    for x, (n, _k, role, _p, _o) in zip(xs, CAST):
        cx = int(r.project((x, 0, 0))[0] * S)
        a = f_name.render(n, True, ORANGE if n == "UCILEV" else INK)
        b = f_role.render(role, True, DIM)
        y = H * S + 100
        sheet.blit(a, (cx - a.get_width() // 2, y))
        sheet.blit(b, (cx - b.get_width() // 2, y + 40))
    pygame.image.save(sheet, os.path.join(out_dir, "cast_lineup.png"))

    # ── 2D vs 3D comparison ──
    CW, BODY, HEAD = 300, 440, 200        # column width, body row, head row heights
    comp = pygame.Surface((CW * len(CAST), 90 + BODY + HEAD + 70))
    comp.fill((21, 24, 30))
    t = f_title.render("2D CUTSCENE  vs  3D RIG", True, INK)
    comp.blit(t, (30, 10))
    pygame.draw.rect(comp, ORANGE, (30, 78, t.get_width(), 5))
    for i, (n, key, role, pose, _o) in enumerate(CAST):
        x0 = i * CW
        # 2D full body (left half) - figure_kit at a scale that matches the 3D height
        body2d = pygame.Surface((CW // 2, BODY)); body2d.fill(BG)
        fk.draw_character(body2d, key, CW // 4, BODY - 20, scale=1.25)
        comp.blit(body2d, (x0, 90))
        # 3D full body (right half)
        r3 = _render3d(actors[key], CW // 4, BODY // 2, (0.0, 1.05, -5.0), (0.0, 1.0, 0.0), 11.5,
                       light, yaw=192.0, pose=pose)
        comp.blit(pygame.transform.scale(r3.surface, (CW // 2, BODY)), (x0 + CW // 2, 90))
        # heads: 2D crop (left) / 3D close-up (right)
        big = pygame.Surface((CW // 2, 900)); big.fill(BG)
        fk.draw_character(big, key, CW // 4, 880, scale=3.0 * 258 / fk.HEIGHT[key] * 0.95)
        top = 880 - int(3.0 * 258 * 0.95) - 40
        comp.blit(big, (x0, 90 + BODY), pygame.Rect(0, max(0, top), CW // 2, HEAD))
        _, j, _ = actors[key].pose_world(POSES["stand"], (0, 0, 0), 192.0, rifle_on=False)
        hx, hy, hz = j["head"]
        rh = _render3d(actors[key], CW // 4, HEAD // 2, (hx + 0.12, hy + 0.04, hz - 1.25),
                       (hx, hy - 0.02, hz), 22, light, yaw=192.0)
        comp.blit(pygame.transform.scale(rh.surface, (CW // 2, HEAD)), (x0 + CW // 2, 90 + BODY))
        pygame.draw.line(comp, (21, 24, 30), (x0, 90), (x0, 90 + BODY + HEAD), 3)
        a = f_name.render(n, True, ORANGE if n == "UCILEV" else INK)
        comp.blit(a, (x0 + CW // 2 - a.get_width() // 2, 90 + BODY + HEAD + 12))
    pygame.image.save(comp, os.path.join(out_dir, "cast_compare.png"))

    # ── 3D portraits ──
    for n, key, _r, _p, _o in CAST:
        P = 360
        _, j, _ = actors[key].pose_world(POSES["stand"], (0, 0, 0), 196.0, rifle_on=False)
        hx, hy, hz = j["head"]
        rp = _render3d(actors[key], P, P, (hx + 0.42, hy + 0.02, hz - 1.45), (hx, hy - 0.16, hz),
                       30, light)
        img = pygame.Surface((P * 2, P * 2 + 70))
        img.fill((21, 24, 30))
        img.blit(pygame.transform.scale(rp.surface, (P * 2, P * 2)), (0, 0))
        a = f_name.render(n, True, INK)
        img.blit(a, (24, P * 2 + 14))
        pygame.draw.rect(img, ORANGE, (24, P * 2 + 8, a.get_width(), 4))
        pygame.image.save(img, os.path.join(out_dir, n.lower() + ".png"))
    print("backend:", r.backend, "->", out_dir)


if __name__ == "__main__":
    render()
