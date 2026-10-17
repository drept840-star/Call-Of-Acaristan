"""make_station_sprites.py - author the hero-interactable sprites.

Regenerates assets/sprites/*.png. The art is flat-shaded pixel work drawn with
pygame primitives at 1:1 (no scaling), palette-locked to the colours the
procedural renderers already use, so the sprites sit invisibly inside the
existing world. Run from the repo root:

    python tools/make_station_sprites.py
"""
import os
import sys
import pygame

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
pygame.init()

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "sprites")
os.makedirs(OUT, exist_ok=True)

# Palette lifted from the game's own comms-wing renderers.
CAB_BODY = (34, 44, 40)
CAB_EDGE = (86, 98, 86)
CAB_DARK = (22, 28, 26)
CAB_DIAL = (118, 142, 110)
CAB_HANDLE = (160, 80, 45)
CAB_SWITCH = (78, 82, 72)
HAZARD_A = (200, 170, 70)
HAZARD_B = (28, 28, 24)
LED_ON = (80, 220, 120)
DESK_WOOD = (48, 43, 36)
DESK_EDGE = (106, 92, 70)
MON_BODY = (10, 18, 18)
MON_EDGE = (66, 95, 88)
CRT = (60, 150, 105)
CRT_BRIGHT = (120, 235, 170)
CHAIR = (32, 38, 38)
CHAIR_EDGE = (70, 78, 74)
GLASS = (30, 55, 58)
GLASS_EDGE = (90, 130, 132)
PAPER = (105, 98, 74)
SHADOW = (0, 0, 0, 75)


def battery_backup():
    w, h = 62, 86
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    # floor shadow
    pygame.draw.ellipse(s, SHADOW, (2, h - 10, w - 4, 10))
    # body + frame
    body = pygame.Rect(2, 2, w - 4, h - 12)
    pygame.draw.rect(s, CAB_BODY, body, border_radius=4)
    pygame.draw.rect(s, CAB_EDGE, body, 2, border_radius=4)
    # hazard band across the top
    for i in range(0, body.w, 10):
        pygame.draw.polygon(s, HAZARD_A if (i // 10) % 2 == 0 else HAZARD_B,
                            [(body.x + i, body.y + 4), (body.x + i + 6, body.y + 4),
                             (body.x + i + 2, body.y + 12), (body.x + i - 4, body.y + 12)])
    pygame.draw.line(s, CAB_EDGE, (body.x, body.y + 13), (body.right, body.y + 13), 1)
    # three gauge dials with needles
    for i, gy in enumerate((body.y + 26, body.y + 44, body.y + 62)):
        pygame.draw.circle(s, CAB_DARK, (body.x + 16, gy), 8)
        pygame.draw.circle(s, CAB_DIAL, (body.x + 16, gy), 8, 1)
        pygame.draw.line(s, CAB_HANDLE, (body.x + 16, gy), (body.x + 22, gy - 3 + i), 1)
        pygame.draw.rect(s, CAB_SWITCH, (body.x + 32, gy - 6, 12, 12), border_radius=1)
        pygame.draw.line(s, CAB_DARK, (body.x + 34, gy - 2), (body.x + 42, gy - 2), 1)
        pygame.draw.line(s, CAB_DARK, (body.x + 34, gy + 2), (body.x + 42, gy + 2), 1)
    # vent slots at the foot
    for i in range(4):
        pygame.draw.line(s, CAB_DARK, (body.x + 8, body.bottom - 8 + i * 2),
                         (body.right - 8, body.bottom - 8 + i * 2), 1)
    # status LED + tiny label plate
    pygame.draw.circle(s, LED_ON, (body.right - 8, body.y + 20), 2)
    pygame.draw.rect(s, (150, 125, 55), (body.x + 30, body.y + 16, 14, 7), border_radius=1)
    pygame.draw.line(s, (60, 50, 20), (body.x + 32, body.y + 19), (body.x + 42, body.y + 19), 1)
    return s


def security_booth():
    w, h = 165, 106
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    desk = pygame.Rect(0, 48, 165, 44)
    mon = pygame.Rect(14, 24, 42, 25)
    chair = pygame.Rect(98, 62, 24, 24)
    # shadows
    pygame.draw.ellipse(s, SHADOW, (desk.x - 6, desk.y + 46, desk.w + 12, 14))
    pygame.draw.ellipse(s, (0, 0, 0, 60), (chair.x - 2, chair.y + 20, 28, 10))
    # glass partition behind the desk (booth reads as a booth)
    glass = pygame.Rect(4, 6, 120, 42)
    pane = pygame.Surface(glass.size, pygame.SRCALPHA)
    pygame.draw.rect(pane, GLASS, pane.get_rect(), border_radius=3)
    pygame.draw.rect(pane, GLASS_EDGE, pane.get_rect(), 1, border_radius=3)
    for off in range(-40, 90, 14):
        pygame.draw.line(pane, (120, 165, 165, 55), (off, 0), (off + 60, glass.h), 1)
    pygame.draw.line(pane, GLASS_EDGE, (60, 0), (60, glass.h), 1)
    s.blit(pane, glass.topleft)
    # CRT monitor with live glow
    pygame.draw.rect(s, MON_BODY, mon, border_radius=3)
    pygame.draw.rect(s, MON_EDGE, mon, 1, border_radius=3)
    pygame.draw.rect(s, CRT, (mon.x + 4, mon.y + 4, mon.w - 8, mon.h - 8), border_radius=2)
    for i in range(3):
        pygame.draw.line(s, CRT_BRIGHT, (mon.x + 7, mon.y + 8 + i * 5),
                         (mon.x + 7 + (22, 14, 26)[i], mon.y + 8 + i * 5), 1)
    pygame.draw.circle(s, LED_ON, (mon.right - 5, mon.y + 5), 2)
    pygame.draw.rect(s, (24, 28, 28), (mon.x + 16, mon.bottom, 10, 4))
    # desk slab + edge highlight
    pygame.draw.rect(s, DESK_WOOD, desk, border_radius=4)
    pygame.draw.rect(s, DESK_EDGE, desk, 2, border_radius=4)
    pygame.draw.line(s, (140, 122, 92), (desk.x + 4, desk.y + 3), (desk.right - 4, desk.y + 3), 1)
    # keyboard wedge, papers, coffee ring
    pygame.draw.polygon(s, (58, 54, 44), [(desk.x + 62, desk.y + 10), (desk.x + 108, desk.y + 10),
                                          (desk.x + 114, desk.y + 24), (desk.x + 56, desk.y + 24)])
    for i in range(3):
        pygame.draw.line(s, (90, 86, 68), (desk.x + 64 + i * 2, desk.y + 13 + i * 3),
                         (desk.x + 106 + i * 2, desk.y + 13 + i * 3), 1)
    pygame.draw.rect(s, PAPER, (desk.x + 120, desk.y + 8, 16, 10))
    pygame.draw.rect(s, PAPER, (desk.x + 126, desk.y + 14, 16, 10))
    pygame.draw.line(s, (70, 64, 48), (desk.x + 122, desk.y + 12), (desk.x + 134, desk.y + 12), 1)
    pygame.draw.circle(s, (66, 58, 44), (desk.x + 34, desk.y + 16), 6, 1)
    # auth terminal keypad the player actually presses
    pad = pygame.Rect(desk.x + 138, desk.y + 22, 20, 14)
    pygame.draw.rect(s, (20, 26, 24), pad, border_radius=2)
    pygame.draw.rect(s, (120, 165, 140), pad, 1, border_radius=2)
    for r in range(2):
        for c in range(3):
            pygame.draw.rect(s, (95, 130, 110), (pad.x + 3 + c * 6, pad.y + 3 + r * 5, 4, 3))
    # chair
    pygame.draw.rect(s, CHAIR, chair, border_radius=4)
    pygame.draw.rect(s, CHAIR_EDGE, chair, 1, border_radius=4)
    pygame.draw.line(s, CHAIR_EDGE, (chair.x + 4, chair.y + 8), (chair.right - 4, chair.y + 8), 1)
    pygame.draw.line(s, (24, 28, 28), (chair.centerx, chair.bottom), (chair.centerx, chair.bottom + 8), 2)
    pygame.draw.line(s, (24, 28, 28), (chair.centerx - 8, chair.bottom + 8),
                     (chair.centerx + 8, chair.bottom + 8), 2)
    return s


for name, fn in (("station_battery_backup.png", battery_backup),
                 ("station_security_booth.png", security_booth)):
    surf = fn()
    path = os.path.join(OUT, name)
    pygame.image.save(surf, path)
    print(f"wrote {os.path.normpath(path)}  {surf.get_width()}x{surf.get_height()}  "
          f"{os.path.getsize(path)} bytes")

