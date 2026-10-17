import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import pygame
pygame.init()
from core.config import WIDTH, HEIGHT
screen = pygame.display.set_mode((WIDTH, HEIGHT))
from core.state import STATE
from missions.m5 import draw as d
from cutscenes import m5mid3d
OUT = os.path.join(ROOT, "_shots", "outfit")
STATE.active_mission = None
a = d._dialogue_portrait("BIRIBEL", (225, 228, 232), 96)
STATE.active_mission = "MISSION5"; STATE.m5_outfit = "guard"
b = d._dialogue_portrait("BIRIBEL", (225, 228, 232), 96)
s = pygame.Surface((200, 96)); s.blit(a, (0, 0)); s.blit(b, (104, 0))
pygame.image.save(pygame.transform.scale(s, (600, 288)), os.path.join(OUT, "portrait_cmp.png"))
m5mid3d.draw_m5x_2d("m5x_faces_wide", screen, 0)
pygame.image.save(screen, os.path.join(OUT, "2d_m5x_faces_wide_0.png"))
print("ok")
