"""Render stills for the M5 outfit change into _shots/outfit/ (dev aid)."""
import os, sys, time
os.environ.setdefault("ACARISTAN_RENDERER", "software")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import pygame
pygame.init()
from core.config import WIDTH, HEIGHT
screen = pygame.display.set_mode((WIDTH, HEIGHT))
OUT = os.path.join(ROOT, "_shots", "outfit")
os.makedirs(OUT, exist_ok=True)
from cutscenes import m5mid3d, m5martial3d

which = sys.argv[1] if len(sys.argv) > 1 else "all"
SHOTS = [("m5x_decree", 2000), ("m5x_change", 600), ("m5x_change", 1400), ("m5x_change", 2300),
         ("m5x_change", 4400), ("m5x_barracks", 3600), ("m5x_faces_release", 1500),
         ("m5x_pw_arrival_door", 2000), ("m5x_vasile_close", 1500), ("m5x_vasile_biribel", 1500),
         ("m5x_maru_biribel", 1500), ("m5x_breach", 2000)]
END = [("m5_radio", 3000), ("m5_river_gate", 2500)]
if len(sys.argv) > 2:
    SHOTS = [s for s in SHOTS if s[0] in sys.argv[2].split(",")]
    END = [s for s in END if s[0] in sys.argv[2].split(",")]


def save(name):
    pygame.image.save(screen, os.path.join(OUT, name + ".png"))


if which in ("all", "3d"):
    for sc, t in SHOTS:
        t0 = time.perf_counter()
        m5mid3d.draw_m5x(sc, screen, t)
        print(sc, t, "%.0f ms" % ((time.perf_counter() - t0) * 1000))
        save("%s_%d" % (sc, t))
    for sc, t in END:
        m5martial3d.draw_m5_scene_3d(sc, screen, t)
        save("%s_%d" % (sc, t))
    print("3d failed?", m5martial3d._cache.get("failed"), m5martial3d._cache.get("err"))
if which in ("all", "2d"):
    for sc, t in (("m5x_change", 600), ("m5x_change", 3000), ("m5x_faces_wide", 0), ("m5x_vasile_wide", 0)):
        m5mid3d.draw_m5x_2d(sc, screen, t)
        save("2d_%s_%d" % (sc, t))
    from cutscenes import m5martial
    m5martial._draw_m5_radio(screen, 3000)
    save("2d_m5_radio")
if which in ("all", "game"):
    from core.state import STATE
    from core import outfits
    from entities.player import Player
    from missions.m5 import draw as m5draw
    STATE.active_mission = "MISSION5"
    STATE.m5_outfit = "guard"
    surf = pygame.Surface((360, 120))
    surf.fill((44, 46, 50))
    p = Player(40, 40)
    p.angle = 0.0
    p.story_outfit = outfits.gameplay_outfit(STATE)
    p.draw(surf, 0, 0)
    p2 = Player(40, 40)
    p2.angle = 0.0
    p2.draw(surf, -60, 0)        # saved look, no outfit (reference)

    class _E:
        pass
    for i, kind in enumerate(("raider", "rifle", "marksman")):
        e = _E()
        e.rect = pygame.Rect(180 + i * 60, 40, 32, 32)
        e.angle = 0.0
        e.m5_type = kind
        m5draw._draw_m5_guard(surf, e, 0, 0)
    big = pygame.transform.scale(surf, (1080, 360))
    pygame.image.save(big, os.path.join(OUT, "game_sprites.png"))
    g = big.copy()
    for y in range(g.get_height()):
        for x in range(g.get_width()):
            r, gg, b, _ = g.get_at((x, y))
            l = int(0.299 * r + 0.587 * gg + 0.114 * b)
            g.set_at((x, y), (l, l, l))
    pygame.image.save(g, os.path.join(OUT, "game_sprites_gray.png"))
    port = m5draw._dialogue_portrait("BIRIBEL", (225, 228, 232), 96)
    pygame.image.save(port, os.path.join(OUT, "portrait_biribel.png"))
    print("saved look untouched:", p.look, p._rk["uniform"])
print("done")
