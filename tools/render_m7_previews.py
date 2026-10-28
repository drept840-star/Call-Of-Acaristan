import os,sys
from pathlib import Path
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
os.environ['ACARISTAN_RENDERER']='software'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import pygame
from cutscenes import m7films as films, m7world3d as F, m6world3d as W
from core.outfits import OUTFIT_GUARD
from engine3d import POSES
from engine3d.hold import hold_weapon
from missions.m7 import farmyard as FY
pygame.display.set_mode((1000,700))
s=pygame.Surface((1000,700))
out=Path('/home/user/previews')
for name,fn,t in [('intro-field',films.dropoff_field,2100),('intro-helicopter',films.dropoff_lift,1400)]:
 fn(s,t);pygame.image.save(s,str(out/(name+'.png')))
key=('biribel',OUTFIT_GUARD)
hum=W.hum(key,flags=('shotgun',))
for mode in ('ready','aim'):
 r,buf=F.stage('dawn',1000,(2.0,1.65,2.5),(0,1.15,0.15),36,seed=23)
 pose=hold_weapon(hum,dict(POSES['ready']),(0,0,0),0,'shotgun',mode)
 W.actor(r,key,pose,(0,0,0),0,1000,amp=0,rifle_on=True,flags=('shotgun',))
 F.finish(s,r,buf,23,'M7',1000)
 pygame.image.save(s,str(out/('shotgun-'+mode+'.png')))
FY.begin(FY.PREP,lambda:None)
FY._S['lines']=[]
FY._S['after']=None
FY._h_tractor()
FY.draw(s)
pygame.image.save(s,str(out/'tractor.png'))
FY._finish_tractor()
FY._S['lines']=[]
FY.draw(s)
pygame.image.save(s,str(out/'tractor-parked.png'))
print('Rendered six previews')
