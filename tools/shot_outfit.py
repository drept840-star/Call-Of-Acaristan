"""Polish pass Task 5 evidence: Biribel's M5 Guard kit in every view.

    python tools/shot_outfit.py OUTDIR

Writes into OUTDIR:
  gameplay_<stage>.png       full M5 frame per stage (HQ day / Quarter night+rain /
                             Print Works / Raid / Tunnel) + a 4x crop on Biribel
  sprites.png                gameplay sprite: pre-change saved look vs the Guard kit
                             over every shop palette and head (the kit must win)
  figure2d.png               2D figure_kit (cutscene fallback) pre/post change +
                             the in-mission dialogue portrait
and prints the mean torso colour of the gameplay sprite per stage (b-r > 12
means it reads blue).
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, os.environ.get("ACA_POLISH_SRC", str(ROOT / "src")))

import pygame  # noqa: E402
from core import config  # noqa: E402


def _crop(surf, cx, cy, r=40, z=4):
    rect = pygame.Rect(int(cx - r), int(cy - r), 2 * r, 2 * r).clip(surf.get_rect())
    return pygame.transform.scale(surf.subsurface(rect).copy(), (rect.w * z, rect.h * z))


def _torso_mean(surf, cx, cy, r=7):
    tot = [0, 0, 0]
    n = 0
    for y in range(int(cy - r), int(cy + r)):
        for x in range(int(cx - r), int(cx + r)):
            c = surf.get_at((x, y))
            tot[0] += c.r; tot[1] += c.g; tot[2] += c.b; n += 1
    return tuple(v // max(1, n) for v in tot)


def gameplay(out):
    from core.state import STATE
    from missions import m5
    from missions.m5 import draw as d, flow
    starts = [("hq", m5.start_mission5_hq_checkpoint),
              ("quarter", m5.start_mission5_quarter_checkpoint),
              ("printworks", m5.start_mission5_printworks_checkpoint),
              ("raid", None),
              ("tunnel", m5.start_mission5_tunnel_checkpoint)]
    W, H = config.screen.get_size()
    for name, start in starts:
        if start is None:
            m5.start_mission5_printworks_checkpoint()
            try:
                flow._begin_raid()
            except Exception as e:  # noqa: BLE001 - evidence only
                print("raid skipped:", e)
                continue
        else:
            start()
        STATE.enemies = []
        STATE.m5_dialogue_active = False
        STATE.player.angle = 0.6
        px, py = STATE.player.rect.center
        cam_x, cam_y = px - W // 2, py - H // 2
        for _ in range(3):
            d.game_draw(cam_x, cam_y)
        pygame.image.save(config.screen, str(out / ("gameplay_%s.png" % name)))
        pygame.image.save(_crop(config.screen, W // 2, H // 2),
                          str(out / ("gameplay_%s_crop.png" % name)))
        print("%-11s stage=%-12s outfit=%s torso=%s" % (
            name, getattr(STATE, "mission5_stage", "?"), STATE.player.story_outfit,
            _torso_mean(config.screen, W // 2, H // 2)))


def sprites(out):
    from core import appearance as ap, outfits
    from entities.player import Player
    pals = list(ap.PALETTES)
    heads = list(ap.HEADGEARS)
    cell = 72
    rows = [("saved", None)] + [("guard", outfits.OUTFIT_GUARD)]
    sheet = pygame.Surface((cell * max(len(pals), len(heads)) * 2, cell * 2 * len(rows) * 2))
    sheet.fill((92, 94, 96))
    y = 0
    for label, outfit in rows:
        for line in (pals, heads):
            for i, item in enumerate(line):
                p = Player(0, 0)
                look = ap.make(palette=item if item in ap.PALETTES else None,
                               head=item if item in ap.HEADGEARS else None)
                p.set_appearance(look)
                p.story_outfit = outfit
                p.angle = -1.2
                tile = pygame.Surface((cell, cell))
                tile.fill((92, 94, 96))
                p.draw(tile, p.rect.centerx - cell // 2, p.rect.centery - cell // 2)
                sheet.blit(pygame.transform.scale(tile, (cell * 2, cell * 2)), (i * cell * 2, y))
            y += cell * 2
    pygame.image.save(sheet, str(out / "sprites.png"))


def figure2d(out):
    from core import outfits
    from core.state import STATE
    from cutscenes.figure_kit import draw_character
    from missions.m5 import draw as d
    s = pygame.Surface((900, 420))
    s.fill((60, 62, 66))
    for i, o in enumerate((outfits.OUTFIT_KRAP, "krap_armband", outfits.OUTFIT_GUARD)):
        draw_character(s, "biribel", 120 + i * 220, 400, 1.2, True,
                       wardrobe=outfits.biribel_2d(o) or None)
    STATE.active_mission = "MISSION5"
    STATE.m5_outfit = outfits.OUTFIT_GUARD
    d._PORTRAITS.clear()
    por = d._dialogue_portrait("BIRIBEL", (120, 170, 230), 96)
    s.blit(pygame.transform.scale(por, (192, 192)), (690, 120))
    pygame.image.save(s, str(out / "figure2d.png"))


def main(argv):
    out = ROOT / argv[0]
    out.mkdir(parents=True, exist_ok=True)
    gameplay(out)
    sprites(out)
    figure2d(out)
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1:])
