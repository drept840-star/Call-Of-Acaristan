"""M5 laser integration and stair landing regression, both renderer backends."""
import os
from pathlib import Path
import sys
from unittest.mock import patch
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def main():
    import numpy as np
    import pygame
    from core import config
    from cutscenes import m5mid3d as mid, m5shadow3d as finale
    out=ROOT/'outputs'/'laser_stair_check'/os.environ.get('ACARISTAN_RENDERER','auto')
    out.mkdir(parents=True,exist_ok=True)
    screen=pygame.Surface(config.screen.get_size())
    for wounded, arrival in ((False,3600),(True,3800)):
        stopped_z,stopped_pose=mid._stair_actor(arrival,wounded)
        assert stopped_z==6.0 and mid._stair_height(stopped_z)==0
        for ms in range(arrival,5201,33):
            z,pose=mid._stair_actor(ms,wounded)
            assert z==stopped_z and pose==stopped_pose,(wounded,ms,'Walking in place')
            assert all(pose[n]==0 for n in ('lhip_p','rhip_p','lkn','rkn'))
        samples=[mid._stair_actor(ms,wounded)[0] for ms in range(0,4201,20)]
        assert samples==sorted(samples) and max(samples)==6
    assert mid._stair_actor(2000,True)[0]<mid._stair_actor(2000)[0]
    mid._basement_descent(screen,4100)
    pygame.image.save(screen,str(out/'stair_landed.png'))
    print('Both actors reach the floor and remain planted: OK')
    real=finale._laser_sight
    def dot_only(s,r,dot,muzzle,t,power=None):
        return real(s,r,dot,None,t,power)
    for ms in (10500,15000,24000):
        with patch.object(finale,'_laser_sight',wraps=real) as laser:
            finale.draw(screen,ms)
            assert laser.call_count==1
            assert laser.call_args.args[3] is not None,'Missing rifle emitter'
        full=pygame.surfarray.array3d(screen).copy()
        pygame.image.save(screen,str(out/('laser_%05d.png'%ms)))
        with patch.object(finale,'_laser_sight',side_effect=dot_only):
            finale.draw(screen,ms)
        base=pygame.surfarray.array3d(screen)
        mask=np.abs(full.astype(int)-base.astype(int)).sum(axis=2)>8
        xs,ys=np.nonzero(mask)
        assert len(xs)>80 and max(int(xs.max()-xs.min()),int(ys.max()-ys.min()))>80,(ms,'Still only a dot')
        assert ys.min()>=finale.TOP and ys.max()<finale.BOT,'Beam leaked into letterbox'
        print('Production laser',ms,'beam pixels:',len(xs))
    for ms in (0,6900,31000,41000):
        with patch.object(finale,'_laser_sight',wraps=real) as laser:
            finale.draw(screen,ms)
            assert not laser.called,'Laser outside authored interval'
    print('LASER AND STAIR CHECK: OK')


if __name__=='__main__':main()
