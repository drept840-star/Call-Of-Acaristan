#!/usr/bin/env python3
"""AE PROOF3D - render the fixed Phase 11 proof scenes to PNGs.

    python3 tools/ae_proof3d.py --out previews/upgrades3d/before

Scenes (fixed t, fixed cameras - comparable across steps):
  office.png  cutscenes.m5mid3d Vasile office wide (set data + humanoids)
  depot.png   missions.m0 depot 3D outro shot (set data)
  film.png    missions.m2.sniper3d ambush film frame (humanoids)
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _faces(surf, out):
    """Step-8 proof: one cast face per panel - expressions, talking
    mouth, look-at - through engine3d's real Humanoid/build path."""
    import pygame

    from cutscenes.cast3d import humanoid3d
    from engine3d import Renderer
    from engine3d.rig import mouth_flap, solve_look

    panels = [("neutral", 0.0, None), ("smile", 0.0, None),
              ("angry", 0.0, None), ("sad", 0.0, None),
              ("surprised", 0.0, None), ("talking", None, None),
              ("look left", 0.0, (-0.55, 1.58, 0.4)),
              ("look down-right", 0.0, (0.55, 1.25, 0.4))]
    pw, ph = 250, 250
    grid = pygame.Surface((pw * 4, ph * 2))
    font = pygame.font.SysFont("arial", 20, bold=True)
    hum = humanoid3d("vasile", hair=(118, 112, 106), skin=(176, 136, 108),
                     brow_t=5, head_w=1.1, stubble=True, stubble_t=0.16,
                     creases=(128, 94, 76), iris=(34, 44, 62))
    for i, (name, mouth, look) in enumerate(panels):
        r = Renderer(pw, ph)
        buf = pygame.Surface((pw, ph))
        buf.fill((24, 26, 32))
        r.set_camera((0.14, 1.68, 1.25), (0, 1.55, 0), 38)
        r.begin()
        expr = "neutral" if name == "talking" else name.split()[0]
        hum.set_expression(expr, mouth_flap(1250, 3) if name == "talking"
                           else (mouth or 0.0))
        pose = {}
        if look:
            hy, hp = solve_look((0, 1.6, 0), look, 0)
            pose = {"head_y": hy, "head_p": hp}
        verts, faces, _j = hum.build(pose, (0, 0, 0), 0)
        r.add_dynamic(verts, faces)
        r.flush(buf)
        grid.blit(buf, ((i % 4) * pw, (i // 4) * ph))
        tag = font.render(name, True, (235, 230, 215))
        grid.blit(tag, ((i % 4) * pw + 10, (i // 4) * ph + 8))
    pygame.image.save(grid, os.path.join(out, "faces.png"))
    hum.set_expression("neutral", 0.0)


def _anim(surf, out):
    """Step-10 proof: the depot at three shot times - the monitor's
    emissive colour/intensity and the lamp sway are timeline-expression
    driven, so the frames must differ (and repeat exactly)."""
    import pygame

    from missions import m0

    strip = pygame.Surface((1000, 3 * 200))
    font = pygame.font.SysFont("arial", 20, bold=True)
    for i, t in enumerate((900, 1700, 2500)):
        m0._draw_depot3d(surf, t)
        crop = surf.subsurface((0, 290, 1000, 200)).copy()
        strip.blit(crop, (0, i * 200))
        tag = font.render(f"t={t} ms", True, (235, 230, 215))
        strip.blit(tag, (10, i * 200 + 8))
    pygame.image.save(strip, os.path.join(out, "anim_strip.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--post", action="store_true",
                    help="apply the Phase 11 step-5 post stack (depot via its timeline data)")
    ap.add_argument("--weather", action="store_true",
                    help="also render the M0 yard with weather on/off (step 6)")
    ap.add_argument("--faces", action="store_true",
                    help="also render the step-8 expression/look-at face grid")
    ap.add_argument("--anim", action="store_true",
                    help="also render the step-10 animated-props time strip")
    args = ap.parse_args()
    sys.path.insert(0, os.path.join(ROOT, "src"))
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    surf = pygame.display.set_mode((1000, 700))

    os.makedirs(args.out, exist_ok=True)
    from cutscenes import m5mid3d
    m5mid3d._vasile_wide(surf, 1200)
    if args.post:
        from cutscenes.post3d import apply_post
        apply_post(surf, {"grade": "night_warm", "grain": 0.3, "vignette": 0.55,
                          "bloom": 0.55, "distortion": 0.012}, 1200, "proof_office", 4000)
    pygame.image.save(surf, os.path.join(args.out, "office.png"))

    from missions import m0
    if args.post:
        # depot through the real dispatcher: timeline post data + DOF
        from cutscenes import draw_cutscene_scene
        from game import timelines
        shot = next(s for s in timelines.shots("mission0.outro", [])
                    if s.get("scene") == "m0_depot3d")
        draw_cutscene_scene(surf, dict(shot), 1600)
    else:
        m0._draw_depot3d(surf, 1600)
    pygame.image.save(surf, os.path.join(args.out, "depot.png"))

    if args.weather:
        from core.user_settings import SETTINGS
        from cutscenes import draw_cutscene_scene
        from game import timelines
        shot = next(s for s in timelines.shots("mission0.outro", [])
                    if s.get("scene") == "m0_yard3d")
        old = SETTINGS.quality_3d
        SETTINGS.quality_3d = 0
        draw_cutscene_scene(surf, dict(shot), 1800)
        pygame.image.save(surf, os.path.join(args.out, "yard_off.png"))
        SETTINGS.quality_3d = 2
        draw_cutscene_scene(surf, dict(shot), 1800)
        pygame.image.save(surf, os.path.join(args.out, "yard.png"))
        SETTINGS.quality_3d = old
    if args.faces:
        _faces(surf, args.out)
    if args.anim:
        _anim(surf, args.out)
    os.environ["ACARISTAN_RENDERER"] = "software"
    from missions.m2.sniper3d import SniperCinematic
    c = SniperCinematic()
    c.t = c.shots[-1][1] * 0.45
    c.draw(surf)
    if args.post:
        from cutscenes.post3d import apply_post
        fs = pygame.Surface((1000, 700))
        fs.blit(pygame.transform.smoothscale(c.r.surface, (1000, 700)), (0, 0))
        apply_post(fs, {"grade": "cold_blue", "grain": 0.4, "vignette": 0.6,
                        "bloom": 0.4}, 900, "proof_film", 4000)
        pygame.image.save(fs, os.path.join(args.out, "film.png"))
        print(f"AE PROOF3D: OK (3 scenes + post -> {args.out})")
        return 0
    pygame.image.save(c.r.surface, os.path.join(args.out, "film.png"))
    print(f"AE PROOF3D: OK (3 scenes -> {args.out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
