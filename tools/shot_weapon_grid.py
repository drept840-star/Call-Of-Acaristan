"""Polish pass Task 4: weapon-attachment verification grid.

    python tools/shot_weapon_grid.py OUTDIR [--debug] [--weapon k9_smg|os12|pistol]

Rows: {default outfit, KRAP (saved KRAP Slate look), Guard black (M5 story
outfit)} x {idle, walk, fire, reload}; columns: 8 aim directions. Each cell
is drawn on the dark M5 Print Works floor tone at 3x. --debug turns on the
rig overlay (body/shoulders/hands/grip). Prints the worst grip-to-hands
distance per outfit (the smoke check holds it to the same numbers).
Writes OUTDIR/weapon_grid.png (+ weapon_grid_debug.png with --debug).
"""
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ACA_FREEZE", "1")
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, os.environ.get("ACA_POLISH_SRC", str(ROOT / "src")))

import pygame  # noqa: E402
from core import config  # noqa: E402,F401

CELL, Z = 64, 3
FLOOR = (44, 40, 36)
OUTFITS = (("default", "pal_olive", None), ("krap", "pal_krap", None),
           ("guard", "pal_olive", "guard"))
STATES = ("idle", "walk", "fire", "reload")


def grip_error(an):
    """Distance from the grip to the nearest point between the two hands."""
    (lx, ly), (rx, ry), (gx, gy) = an["hand_l"], an["hand_r"], an["grip"]
    mx, my = (lx + rx) / 2, (ly + ry) / 2
    return math.hypot(gx - mx, gy - my)


def render(player, state, angle, debug=False):
    from core.state import STATE
    tile = pygame.Surface((CELL, CELL))
    tile.fill(FLOOR)
    player.angle = angle
    player.debug_rig = debug
    kw = {}
    if state == "walk":
        for _ in range(6):
            player.draw(pygame.Surface((CELL, CELL)), player.rect.centerx - CELL // 2,
                        player.rect.centery - CELL // 2, is_moving=True)
        kw["is_moving"] = True
    elif state == "fire":
        player._recoil_timer = 8
        STATE.muzzle_flash_timer = 3
    elif state == "reload":
        kw.update(reload_active=True, reload_progress=0.45)
    player.draw(tile, player.rect.centerx - CELL // 2, player.rect.centery - CELL // 2, **kw)
    if state == "fire":   # muzzle position the game uses for the flash/bullets
        tx, ty = player.barrel_tip()
        pygame.draw.circle(tile, (255, 210, 120),
                           (int(tx - player.rect.centerx + CELL // 2),
                            int(ty - player.rect.centery + CELL // 2)), 2)
    return tile, grip_error(player.rig_anchors)


def main(argv):
    from core import appearance as ap
    from core.state import STATE
    from entities.player import Player
    out = ROOT / argv[0]
    out.mkdir(parents=True, exist_ok=True)
    debug = "--debug" in argv
    weapon = argv[argv.index("--weapon") + 1] if "--weapon" in argv else "k9_smg"
    STATE.current_weapon = weapon
    font = pygame.font.SysFont("consolas", 14)
    lab_w = 120
    W = lab_w + 8 * CELL * Z
    H = len(OUTFITS) * len(STATES) * CELL * Z + 24
    for dbg in ((False, True) if debug else (False,)):
        sheet = pygame.Surface((W, H))
        sheet.fill((20, 20, 22))
        for i in range(8):
            t = font.render("%d deg" % (i * 45), True, (200, 200, 200))
            sheet.blit(t, (lab_w + i * CELL * Z + 6, 4))
        worst = {}
        row = 0
        for name, pal, story in OUTFITS:
            p = Player(100, 100, max_hp=150)
            p.set_appearance(ap.make(palette=pal))
            p.story_outfit = story
            for st in STATES:
                y = 24 + row * CELL * Z
                sheet.blit(font.render("%s / %s" % (name, st), True, (220, 220, 220)), (6, y + 8))
                for i in range(8):
                    tile, err = render(p, st, i * math.pi / 4, dbg)
                    worst[name] = max(worst.get(name, 0.0), err)
                    sheet.blit(pygame.transform.scale(tile, (CELL * Z, CELL * Z)),
                               (lab_w + i * CELL * Z, y))
                row += 1
        fn = "weapon_grid_debug.png" if dbg else "weapon_grid.png"
        pygame.image.save(sheet, str(out / fn))
        print(fn, "weapon=%s" % weapon, "worst grip-to-hands px:",
              {k: round(v, 2) for k, v in worst.items()})


if __name__ == "__main__":
    main(sys.argv[1:])
