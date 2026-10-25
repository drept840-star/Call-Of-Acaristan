"""Melee parity check: render one M6 K-9 swing frame by frame.

    python tools/m6_melee_strip.py [OUT.png]

Calls ``player.draw`` exactly the way ``missions.m6.draw`` calls it (same
kwargs) while ``STATE.melee_timer`` counts down, and stitches the frames
into one strip with the frame's progress value.  Before the fix M6 passed
no ``melee_progress`` at all, so every frame drew the swing's first pose -
this tool is how you see that it now moves.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()

from core.state import STATE             # noqa: E402
from missions import m6                  # noqa: E402
from missions.m6 import draw as _m6draw  # noqa: E402
from missions.m6 import world as _world  # noqa: E402

CELL = (96, 96)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "shots", "m6_melee_strip.png")
    m6.start_m6()
    # Parity with M4/M5: M6 must boot on the K-9 melee, not the pistol butt.
    assert STATE.current_weapon == "k9_smg", STATE.current_weapon
    assert STATE.mission3_weapon == "k9_smg", (
        "M6 booted with melee weapon %r - the first swing would use the "
        "pistol butt instead of the K-9 buttstroke" % (STATE.mission3_weapon,))
    from entities import weapons as _weapons
    _weapons.handle_melee()
    assert STATE.melee_active, "handle_melee did not start a swing"
    assert STATE.melee_timer == 20 and STATE.melee_damage == 62, (
        "K-9 melee is %r frames / %r damage, expected 20 / 62"
        % (STATE.melee_timer, STATE.melee_damage))
    STATE.melee_hit_done = True
    STATE.melee_hit_done = True              # no enemies on the probe map
    STATE.player.angle = 0.0
    p = STATE.player

    frames = []
    seen = set()
    while STATE.melee_timer > 0:
        surf = pygame.Surface(CELL, pygame.SRCALPHA)
        surf.fill((18, 21, 26))
        prog = _m6draw._melee_progress()
        cx, cy = p.rect.centerx, p.rect.centery
        p.draw(surf, cx - CELL[0] // 2, cy - CELL[1] // 2,
               walls=_world.solid_walls(), melee_active=True,
               melee_progress=prog, is_moving=False)
        label = pygame.font.Font(None, 16).render(
            "t=%02d p=%.2f" % (STATE.melee_timer, prog), True, (210, 216, 226))
        surf.blit(label, (3, 3))
        frames.append(surf)
        seen.add(round(prog, 2))
        STATE.melee_timer -= 2                # sample every other frame

    assert len(seen) >= 8, (
        "the swing only showed %d distinct poses (%s) - M6 is drawing the "
        "melee without progress again" % (len(seen), sorted(seen)))
    strip = pygame.Surface((CELL[0] * len(frames), CELL[1]), pygame.SRCALPHA)
    strip.fill((12, 14, 18))
    for i, f in enumerate(frames):
        strip.blit(f, (i * CELL[0], 0))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pygame.image.save(strip, out)
    print("wrote", out, "frames:", len(frames))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
