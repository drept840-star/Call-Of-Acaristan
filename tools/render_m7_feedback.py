"""Render review shots for the Mission 7 feedback pass (software renderer)."""
import os
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
os.environ["ACARISTAN_RENDERER"] = "software"

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pygame
from missions.m7.raid3d import RaidScene
from cutscenes import m7world3d as F

pygame.init()
pygame.display.set_mode((1000, 700))
OUT = Path(__file__).resolve().parents[1] / "previews" / "mission7"
OUT.mkdir(parents=True, exist_ok=True)
FONT = pygame.font.Font(None, 28)


def fresh():
    sc = RaidScene()
    sc._active = True
    sc.phase = "w3"
    sc.t = 18.0
    sc.px, sc.pz, sc.yaw, sc.pitch = -2.0, -4.0, 0.0, -2.0
    sc.body_yaw = 0.0
    sc.brain.alex.update(x=-3.6, z=-0.2, yaw=5.0, spot=None, target_slot=None)
    sc.brain.bodi.update(x=5.0, z=0.2, yaw=350.0)
    return sc


def render(name, title, setup):
    sc = fresh()
    setup(sc)
    canvas = pygame.Surface((1000, 700))
    canvas.fill((4, 7, 14))
    sc.draw(canvas)
    # Opaque caption tab is outside the gameplay HUD area.
    pygame.draw.rect(canvas, (10, 15, 25), (18, 16, 575, 42), border_radius=5)
    pygame.draw.rect(canvas, (221, 158, 70), (18, 16, 5, 42))
    canvas.blit(FONT.render(title, True, (244, 235, 214)), (34, 24))
    pygame.image.save(canvas, str(OUT / f"{name}.png"))
    return canvas


def farm_overview():
    # Wide establishing angle makes the new farm perimeter and field landmarks
    # legible, rather than cropping them out with the close third-person camera.
    canvas = pygame.Surface((1000, 700))
    canvas.fill((4, 7, 14))
    r, buf = F.stage("dawn", 1200, (0, 7, -52), (0, 3, 11), 52,
                     size=(1000, 700), seed=12)
    F.finish(canvas, r, buf, 12, "M7", 1200)
    # Remove cinematic letterbox for the review image so the set dressing is
    # not shrunk inside a second black frame.
    band = canvas.subsurface((0, 86, 1000, 460)).copy()
    frame = pygame.Surface((1000, 510))
    frame.fill((7, 10, 16))
    frame.blit(band, (0, 50))
    pygame.draw.rect(frame, (10, 15, 25), (18, 6, 770, 38), border_radius=5)
    pygame.draw.rect(frame, (221, 158, 70), (18, 6, 5, 38))
    frame.blit(FONT.render("00  Farm overview: field edge, windpump and gate layout", True,
                           (244, 235, 214)), (34, 14))
    pygame.image.save(frame, str(OUT / "00-farm-overview.png"))
    return frame


def farm(sc):
    sc.px, sc.pz, sc.yaw, sc.pitch = 0.0, -5.5, 0.0, -4.0
    sc.brain.alex.update(x=-4.2, z=-0.5, yaw=12.0)
    sc.brain.bodi.update(x=4.5, z=0.7, yaw=350.0)


def arrivals(sc):
    # Show the south truck lane plus the two foot approaches in the same yard view.
    sc.px, sc.pz, sc.yaw, sc.pitch = 0.0, -5.0, 180.0, -1.0
    sc.brain.trucks = [
        dict(x=-1.4, z=-22.0, state="drive", dumped=False, riflemen=3, dog=True),
        dict(x=1.5, z=-31.0, state="drive", dumped=False, riflemen=3, dog=False),
    ]
    for x, z, slot in ((-4.2, 17.5, 1), (3.2, 19.0, 2), (21.8, 0.0, 3)):
        e = sc.brain.add("rifle", x, z, [], 0, 1)
        e.update(live=True, slot=slot, yaw=180.0, moving=False)


def burning(sc):
    sc.px, sc.pz, sc.yaw, sc.pitch = 4.0, -3.0, 8.0, -4.0
    sc.brain.alex.update(x=9.0, z=2.1, yaw=6.0, moving=False, pinned=False)
    sc.brain.bodi.update(x=7.2, z=1.0, yaw=345.0, moving=False, loft=False)
    sc.fire.lit = True
    sc.fire.t0 = sc.t - 10.0
    sc.fire.cells = {(4, 0): sc.t - 8, (5, 0): sc.t - 7, (5, 1): sc.t - 6,
                     (6, 1): sc.t - 5, (6, 0): sc.t - 4, (7, 1): sc.t - 3}
    sc.fire.next_spread = sc.t + 30.0


def alex_ai(sc):
    # A compact readable firing-lane setup: Alex's tactical position is fixed
    # for this target rather than being recomputed every couple of seconds.
    sc.px, sc.pz, sc.yaw, sc.pitch = -4.0, -3.0, 0.0, -4.0
    sc.brain.alex.update(x=-1.8, z=0.2, yaw=30.0, moving=False, spot=(-1.8, 0.2), target_slot=1)
    sc.brain.bodi.update(x=4.2, z=0.4, yaw=340.0)
    for x, z, slot in ((-5.0, 17.0, 1), (2.0, 18.0, 2), (8.0, 21.0, 3)):
        e = sc.brain.add("rifle", x, z, [], 0, 3)
        e.update(live=True, slot=slot, yaw=180.0, moving=False, aim=sc.t)


shots = [
    farm_overview(),
    render("02-entry-routes", "02  Guard approaches: readable foot gates and south truck lane", arrivals),
    render("03-barn-fire", "03  Barn fire: irregular flame tongues, depth-occluded by people", burning),
    render("04-alex-cover", "04  Alex: stable firing lane instead of orbiting Biribel", alex_ai),
]


def north_gate(sc):
    sc.px, sc.pz, sc.yaw, sc.pitch = 0.0, -3.0, 0.0, -3.0
    sc.brain.alex.update(x=-4.0, z=0.0)
    sc.brain.bodi.update(x=4.0, z=0.4)
    for i, x in enumerate((-2.5, 0.0, 2.5), 1):
        e = sc.brain.add("rifle", x, 20.5 + (i % 2), [], 0, 3)
        e.update(live=True, slot=i, yaw=180.0, moving=False)


def orchard_gate(sc):
    sc.px, sc.pz, sc.yaw, sc.pitch = 12.0, -1.0, 90.0, -2.0
    sc.brain.alex.update(x=9.0, z=-2.2)
    sc.brain.bodi.update(x=9.5, z=2.0)
    for i, z in enumerate((-2.0, 1.5, 4.0), 1):
        e = sc.brain.add("rifle", 25.5, z, [], 0, 1)
        e.update(live=True, slot=i, yaw=270.0, moving=False)


def trucks_close(sc):
    sc.px, sc.pz, sc.yaw, sc.pitch = 0.0, -8.0, 180.0, -2.0
    sc.brain.trucks = [
        dict(x=-1.4, z=-18.0, state="drive", dumped=False, riflemen=3, dog=True),
        dict(x=1.5, z=-27.0, state="drive", dumped=False, riflemen=3, dog=False),
    ]


def barn_wide(sc):
    burning(sc)
    sc.px, sc.pz, sc.yaw, sc.pitch = -1.0, -6.0, 2.0, -1.0
    sc.brain.alex.update(x=7.0, z=2.0)
    sc.brain.bodi.update(x=4.8, z=0.0)
    sc.fire.cells = {(4, 0): sc.t - 8, (5, 0): sc.t - 7, (5, 1): sc.t - 6,
                     (6, 1): sc.t - 5, (6, 0): sc.t - 4, (7, 1): sc.t - 3,
                     (3, 1): sc.t - 6, (4, 1): sc.t - 5, (7, 0): sc.t - 2}


def farm_night(sc):
    sc.px, sc.pz, sc.yaw, sc.pitch = -1.5, -4.0, 2.0, -2.0
    sc.brain.alex.update(x=-4.2, z=-0.3)
    sc.brain.bodi.update(x=4.7, z=0.6)


more = [
    render("05-north-gate", "05  North footpath: guards approach through the marked gate", north_gate),
    render("06-orchard-gate", "06  Orchard entrance: the eastern guard approach", orchard_gate),
    render("07-trucks-close", "07  Truck arrival: convoy framed by the south farm entrance", trucks_close),
    render("08-burning-yard-wide", "08  Burning yard: wider view of barn fire and allies", barn_wide),
    render("09-farm-night", "09  Farm at raid hour: buildings, well and perimeter", farm_night),
    shots[0],
]

# Contact sheets are for quick scanning; full-size captures remain alongside them.
contact = pygame.Surface((1600, 1160))
contact.fill((10, 13, 19))
head = pygame.font.Font(None, 38)
contact.blit(head.render("MISSION 7  /  VISUAL FEEDBACK PASS", True, (237, 222, 190)), (36, 22))
for i, im in enumerate(shots):
    x = 20 + (i % 2) * 790
    y = 76 + (i // 2) * 538
    small = pygame.transform.smoothscale(im, (760, 532))
    contact.blit(small, (x, y))
    pygame.draw.rect(contact, (105, 90, 64), (x, y, 760, 532), 2)
pygame.image.save(contact, str(OUT.parent / "mission7_feedback_contact.png"))

more_contact = pygame.Surface((1600, 1698))
more_contact.fill((10, 13, 19))
more_contact.blit(head.render("MISSION 7  /  MORE GAMEPLAY PREVIEWS", True, (237, 222, 190)), (36, 22))
for i, im in enumerate(more):
    x = 20 + (i % 2) * 790
    y = 76 + (i // 2) * 538
    small = pygame.transform.smoothscale(im, (760, 532))
    more_contact.blit(small, (x, y))
    pygame.draw.rect(more_contact, (105, 90, 64), (x, y, 760, 532), 2)
pygame.image.save(more_contact, str(OUT.parent / "mission7_more_previews.png"))
print("Rendered nine full-size Mission 7 previews and two review sheets.")
