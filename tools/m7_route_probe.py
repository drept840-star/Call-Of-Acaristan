"""Collision and safe-dismount regression for the Mission 7 tractor."""
import os, sys
from pathlib import Path
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import pygame
from missions.m7 import farmyard as FY, maps as M, minigames as G
from core.state import STATE
FY.begin(FY.PREP, lambda: None)
walls = [w for w in STATE.walls if not any(w == pygame.Rect(c*64,r*64,64,64) for r,row in enumerate(M.farm_grid()) for c,ch in enumerate(row) if ch == 'T')]
pz=G.TractorPuzzle(M.tractor_route_px(),0)
for i in range(len(pz.route)):
    pz.press(pz.t, pz.step()[6])
    for sample in range(101):
        x,y,ang=pz.pose(pz.t+pz.duration*sample/100)
        img=pygame.transform.rotate(FY._tractor_surface(), -ang)
        mask=pygame.mask.from_surface(img)
        rect=img.get_rect(center=(round(x),round(y)))
        for wall in walls:
            if rect.colliderect(wall):
                solid=pygame.mask.Mask(wall.size,fill=True)
                assert not mask.overlap(solid,(wall.x-rect.x,wall.y-rect.y)), (i,sample,wall)
    pz.update(pz.t+pz.duration)
FY._S['drive']=pz
FY._finish_tractor()
assert not any(STATE.player.rect.colliderect(w) for w in STATE.walls)
print('M7 ROUTE: OK (808 sampled poses; collision-free dismount)')
