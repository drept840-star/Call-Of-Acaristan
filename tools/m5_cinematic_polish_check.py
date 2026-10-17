"""Regression evidence for the M5 noir polish; safe isolated preview only."""
import os,sys,tempfile,math,json
from pathlib import Path
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))

def main():
    with tempfile.TemporaryDirectory() as tmp:
        from core import save_system,settings_store,profile_store
        save_system.SAVE_FILE=tmp+'/save.json'
        settings_store.SAVE_FILE=tmp+'/settings.json'
        profile_store.PROFILE_FILE=tmp+'/profile.json'
        import pygame,numpy as np
        from core.config import WIDTH,HEIGHT
        from core.state import STATE
        from cutscenes import m5martial3d as f,m5ending3d as s,m5fx3d as fx
        STATE.reduced_motion=False
        out=ROOT/'outputs'/'m5_polish_review';out.mkdir(parents=True,exist_ok=True)
        screen=pygame.Surface((WIDTH,HEIGHT))
        samples=[('opening',f._river,900),('tracking',f._river,3500),('maru_reach',f._river,4150),
                 ('river',f._river,6000),('guard',f._river,8000),('scope',f._scope,4600),
                 ('reveal_start',f._reveal,1200),('reveal_push',f._reveal,3200),
                 ('reveal_hold',f._reveal,4400),('reveal_carry',f._reveal,6500),
                 ('exit_walk',f._leaves,1900),('exit_reach',f._leaves,3420),
                 ('exit_cut',f._leaves,3570),('radio',f._radio,3000)]
        report=[]
        for label,fn,t in samples:
            fn(screen,t)
            assert not f._cache['failed'],f._cache['err']
            pygame.image.save(screen,str(out/(label+'.png')))
            pixels=pygame.surfarray.array3d(screen)[:,f.SAFE_TOP:f.SAFE_BOT]
            white=np.mean(np.min(pixels,axis=2)>235)
            assert white<.003,(label,'whiteout',white)
            if label=='exit_cut': assert not np.any(pixels)
            report.append((label,round(float(white),6)))
        # The reveal path cannot have the previous discontinuity at 3450/5200.
        cams=[]
        for t in range(0,8401,100):
            f._reveal(screen,t)
            r,_=f._rend();cams.append(r.cam)
            hum=f._hum('ucilev');pose=f._life_pose(s.reveal_pose(hum,t),t,.65,3)
            yaw=f._yaw_to(f._SNIPER,f._BIRIBEL)+10*f._k(t,900,2200)
            p=hum.pose_world(pose,f._SNIPER,yaw)[1]['head']
            proj=r.project(p)
            assert proj is not None
            assert r.h*.10 < proj[1] < r.h*.70,(t,'head framing',proj)
        assert max(math.dist(a,b) for a,b in zip(cams,cams[1:]))<.07
        # Character wetness hook must add NO sprites.
        class Capture:
            cam=(0,1.6,0);fwd=(0,0,1)
            def __init__(self): self.lines=[];self.sprites=[]
            def add_line3d(self,a,b,*args,**kw): self.lines.append((a,b,kw.get('layer')))
            def add_sprite(self,*args,**kw): self.sprites.append(args)
        cap=Capture();f._wet(cap,None,None,None,None,2000)
        assert not cap.sprites
        for t in range(0,2000,41):
            cap=Capture();fx.rain3d(cap,t,44,surface=lambda x,z:0 if abs(x)<9 and abs(z)<9 else None)
            assert not cap.sprites
            for a,b,layer in cap.lines:
                if layer==2: assert abs(a[1]-.016)<1e-6 and abs(b[1]-.016)<1e-6
        assert s.rain_surface(-16,43) is None
        assert s.rain_surface(-18,38)==9.212
        assert s.rain_surface(5,20) is None
        # Idle must move over time and reach must articulate the wrist.
        assert s.idle_pose(0)!=s.idle_pose(1200)
        assert any(s.blink_at(t,4)>.8 for t in range(0,5200,20))
        hum=f._hum('ucilev');initial=f._yaw_to(f._SNIPER,f._BIRIBEL)+10
        pos,yaw,d,reaching=s.ucilev_block(3500,f._SNIPER,initial)
        p=s.door_reach(hum,s.patrol_carry(hum,d,0),pos,yaw,s.door_handle(-16,9.2,41.65,0),reaching)
        assert abs(p['lwr_p'])>6
        (out/'report.json').write_text(json.dumps(report))
        print('M5 cinematic polish: OK; camera continuity, no whiteout, ground-only impacts, wrist/idle checks')
        print('REVIEW: '+str(out))
if __name__=='__main__':main()
