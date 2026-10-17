"""Ending staging/weapon regressions and native-size visual probes; safe saves."""
import os
from pathlib import Path
import sys
import tempfile
import math
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))

def check_tracking_background(f, config, pygame):
    """Compare geometry-only frames to sky-only frames across the whole turn.

    Exclude actors, rain, glow sprites and grade so they cannot conceal a
    missing set. The upper-central image must contain actual world geometry.
    """
    import numpy as np
    from cutscenes import m5ending3d as s
    r,_=f._rend()
    saved=(r.add_humanoid,r.add_sprite,f._fx.rain3d,f._finish,f._river_world,s.east_quay)
    r.add_humanoid=lambda *a,**kw:{}
    r.add_sprite=lambda *a,**kw:None
    f._fx.rain3d=lambda *a,**kw:None
    f._finish=lambda *a,**kw:None
    def coverage(t):
        f._river_world=saved[4]
        f._river(config.screen,t)
        actual=pygame.surfarray.array3d(config.screen).astype(int)
        f._river_world=lambda *a,**kw:None
        f._river(config.screen,t)
        sky=pygame.surfarray.array3d(config.screen).astype(int)
        f._river_world=saved[4]
        w=config.screen.get_width()
        y0=f.SAFE_TOP+int(f._FILM_H*.05)
        y1=f.SAFE_TOP+int(f._FILM_H*.5)
        mask=np.max(np.abs(actual-sky),axis=2)>3
        return float(mask[int(w*.15):int(w*.85),y0:y1].mean())
    try:
        s.east_quay=lambda *a,**kw:None
        missing=coverage(2800)
        assert missing<.60,('missing-set fixture must fail the coverage gate',missing)
        s.east_quay=saved[5]
        worst=1.0
        for t in list(range(2200,5400,100))+[5399]:
            amount=coverage(t)
            worst=min(worst,amount)
            assert amount>.60,('tracking camera looks off the set',t,amount)
        print('tracking_background_full_turn: OK; minimum geometry coverage %.3f'%worst)
    finally:
        r.add_humanoid,r.add_sprite,f._fx.rain3d,f._finish,f._river_world,s.east_quay=saved


def main():
    with tempfile.TemporaryDirectory(prefix='m5_stage_') as tmp:
        from core import save_system,settings_store,profile_store
        save_system.SAVE_FILE=str(Path(tmp)/'save.json')
        settings_store.SAVE_FILE=str(Path(tmp)/'settings.json')
        profile_store.PROFILE_FILE=str(Path(tmp)/'profile.json')
        import pygame
        from core import config
        from cutscenes import m5martial3d as f,m5ending3d as s
        from engine3d.core import m_apply
        from missions.m5.meta import mission5_ending_shots
        hum=f._hum('ucilev')
        worst=0
        from m5_rifle_clearance import penetration
        for pitch in range(14,53,2):
            for d in (0,.25,.5,.75):
                pose=s.rifle_pose(hum,pitch,d,1)
                j=hum.pose_world(pose,(0,0,0),0)[1]
                target=tuple(a+b for a,b in zip(j['rhand'],m_apply(j['rifle_m'],(0,-.025,.24))))
                gap=math.dist(j['lhand'],target)
                worst=max(worst,gap)
                assert gap<.025,(pitch,d,gap)
                assert penetration(hum,pose)==0,('rifle intersects torso/head/pelvis',pitch,d)
        print('two_hand_grip_and_body_clearance: OK; max error %.5f m'%worst)
        for key, pose in ((f._BIRI_GUARD, f._RADIO), ('vasile', dict(f._RADIO, head_y=12))):
            actor = f._hum(key)
            posed = s.radio_pose(actor, pose)
            places, joints, _, _ = actor.placements(posed, rifle_on=False)
            _, _, H, neck, _, _ = next(p for p in places if p[0] == 2)
            ear = tuple(a+b for a,b in zip(neck,m_apply(H,(-.20,.12,.02))))
            # Receiver has a real exterior palm offset, not a slab centred
            # inside the skin fist. Check the actual drawn earpiece frame.
            world_places, world_joints, root = actor.pose_world(posed,(0,0,0),0,rifle_on=False)
            B, origin = s.handset_frame(actor,posed,(0,0,0),0)
            receiver = tuple(a+b for a,b in zip(origin,m_apply(B,(0,.070,0))))
            ear = tuple(a+b for a,b in zip(ear,root))
            assert math.dist(receiver,ear)<.055,(key,receiver,ear)
            assert math.dist(origin,world_joints['lhand'])>.06
        print('radio_receivers_at_ears: OK')
        initial=f._yaw_to(f._SNIPER,f._BIRIBEL)+10
        assert s.ucilev_block(0,f._SNIPER,initial)[0]==f._SNIPER
        assert abs(s.ucilev_block(0,f._SNIPER,initial)[1]-initial)<.001
        assert s.ucilev_block(3300,f._SNIPER,initial)[0]==s.ucilev_block(4200,f._SNIPER,initial)[0]
        assert s.beat(3300,3500,750)==0 and s.beat(4300,3500,750)==1
        assert s.ucilev_block(4300,f._SNIPER,initial)[0][2]<f._SNIPER[2]+s.ROOF_DOOR_Z
        assert s.ucilev_block(6200,f._SNIPER,initial)[0][2]>f._SNIPER[2]+s.ROOF_DOOR_Z+.8
        assert abs(s.maru_block(5350)[0][0]-s.MARU_PORTAL_X)<.001
        assert s.maru_block(5350)[0][2]<-2.5
        assert s.maru_yaw(5350)==180
        assert s.maru_block(3100)[0] == s.maru_block(3500)[0]
        assert s.maru_move_weight(3300) == 0
        for t in range(0,6801,10):
            pos, _, distance, _ = s.ucilev_block(t,f._SNIPER,initial)
            assert abs(pos[1]-f._SNIPER[1]-s.stair_height(distance))<1e-9
        assert abs(s.ucilev_block(6200,f._SNIPER,initial)[0][1]-(f._SNIPER[1]-1.68))<1e-9
        assert mission5_ending_shots[0]['min_ms']>=9600
        # New authored exit cuts on handle contact, before stair descent.
        assert 3550 < mission5_ending_shots[3]['min_ms'] < 4300
        print('turn_pause_open_enter_and_escape: OK')
        out=ROOT/'outputs'/'m5_restage'
        out.mkdir(parents=True,exist_ok=True)
        for d in (0, .5, 1.0):
            pose = s.patrol_carry(hum, d, 1.0)
            assert penetration(hum, pose) == 0, ('carry intersects torso/head', d)
            _, j2, R2, _ = hum.placements(pose)
            muz = tuple(a - b for a, b in zip(m_apply(R2, (0, 0, 1)), m_apply(R2, (0, 0, 0))))
            assert muz[1] < -0.5, ('muzzle not down in carry', d, muz)
            guard = tuple(a + b for a, b in zip(j2['rhand'], m_apply(R2, (0, -0.03, 0.34))))
            assert math.dist(j2['lhand'], guard) < .025, ('left hand off handguard', d)
        print('patrol_carry_grip_and_clearance: OK')
        # Test the actual production transition, not only its valid endpoints.
        transition_gap = 0.0
        from engine3d.rig import blend
        fixture = blend(s.rifle_pose(hum,52),s.patrol_carry(hum),.5)
        _, fj, fR, _ = hum.placements(fixture)
        ft = tuple(a+b for a,b in zip(fj['rhand'],m_apply(fR,(0,-.0275,.29))))
        assert math.dist(fj['lhand'],ft)>.04,'Known-bad blend no longer exercises the grip regression'
        for t in range(0,8401,60):
            pose = s.reveal_pose(hum,t)
            fold = s.beat(t,5200,1600)
            _, joints, R, _ = hum.placements(pose)
            target = tuple(a+b for a,b in zip(joints['rhand'],m_apply(R,(0,-.025-.005*fold,.24+.10*fold))))
            gap = math.dist(joints['lhand'],target)
            transition_gap = max(transition_gap,gap)
            assert gap<.025,('production lowering loses hand contact',t,gap)
            assert penetration(hum,pose)==0,('production lowering clips body',t)
        print('production_lowering_grip_and_clearance: OK; max error %.5f m'%transition_gap)
        sx,sy,sz=f._SNIPER
        for t in range(0,6801,60):
            pos,yaw,d,reach=s.ucilev_block(t,f._SNIPER,initial)
            moving=max(s.move_weight(t,650,2650),s.move_weight(t,4300,1900))
            pose=s.patrol_carry(hum,d,moving)
            pose=s.door_reach(hum,pose,pos,yaw,(sx-.46,sy+1.26,sz+s.ROOF_DOOR_Z-.15),reach)
            assert penetration(hum,pose)==0,('production walk/door body clipping',t)
        print('production_walk_and_door_clearance: OK')
        # A populated destination with a genuinely open central route.
        meshes=[]
        from types import SimpleNamespace
        recorder=SimpleNamespace(add_dynamic=lambda *a,**kw:None)
        s.quay_destination(recorder,0,lambda r,m: meshes.append(m),lambda *a:None,f._fx)
        inside=[m for m in meshes if all(v[2]<-5.5 for v in m.verts)]
        assert len(inside)>60,('warehouse storage missing',len(inside))
        for z in (-2,-3,-4,-6,-8,-10):
            for m in meshes:
                lo=[min(v[i] for v in m.verts) for i in range(3)]
                hi=[max(v[i] for v in m.verts) for i in range(3)]
                assert not all(lo[i]<p<hi[i] for i,p in enumerate((10.3,1.0,z))),('warehouse aisle blocked',z)
        print('furnished_warehouse_and_clear_aisle: OK')
        check_tracking_background(f,config,pygame)
        probes=[('ots_0900',f._river,900),('east_2200',f._river,2200),('east_2800',f._river,2800),('turn_3200',f._river,3200),('turn_3400',f._river,3400),('track_3600',f._river,3600),('threshold_6000',f._river,6000),('dot_8600',f._river,8600),
                ('scope_2600',f._scope,2600),('scope_4600',f._scope,4600),
                ('lift_1200',f._reveal,1200),('face_3800',f._reveal,3800),('carry_7200',f._reveal,7200),
                ('turn_0900',f._leaves,900),('otsroof_3000',f._leaves,3000),('door_5000',f._leaves,5000),('seam_6600',f._leaves,6600),
                ('radio_3000',f._radio,3000)]
        for name,draw,t in probes:
            draw(config.screen,t)
            pygame.image.save(config.screen,str(out/(name+'.png')))
        assert not f._cache['failed'],repr(f._cache['err'])
        from PIL import Image,ImageDraw
        sheet=Image.new('RGB',(1600,1920),(8,12,18)); label=ImageDraw.Draw(sheet)
        for i,(name,_,_) in enumerate(probes):
            image=Image.open(out/(name+'.png')).convert('RGB')
            image.thumbnail((400,280))
            x,y=i%4*400,i//4*320
            sheet.paste(image,(x,y));label.text((x+8,y+288),name,fill=(220,216,205))
        sheet.save(out/'sheet.jpg',quality=90)
        print('M5 ENDING STAGE CHECK: OK; backend='+str(getattr(f._rend()[0],'backend','?')))
        pygame.quit()

if __name__=='__main__':main()
