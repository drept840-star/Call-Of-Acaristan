import os, sys
os.environ['SDL_VIDEODRIVER'] = 'dummy'; os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, 'src')
import pygame
from core.state import STATE
from core import config
from missions import m5
from missions.m5 import world as w
m5.start_mission5_tunnel_checkpoint()
STATE.enemies = []
m = STATE.m5_maru
px, py = STATE.player.rect.center
m['x'], m['y'] = float(px - 150), float(py + 20)
m['following'] = False
STATE.current_weapon = 'k9_smg'
STATE.k9_ammo_in_mag, STATE.k9_spare_mags = 0, 0
w._update_maru()
for _ in range(22):
    w._update_maru()
cx, cy = m5.game_update(None) if False else (STATE.camera_x, STATE.camera_y)
from missions.m5.systems import _update_camera
cx, cy = _update_camera()
m5.game_draw(cx, cy)
pygame.image.save(config.screen, '_shots/outfit/maru_mags.png')
print('saved')
