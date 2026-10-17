"""Fresh M5 3D finale: geometry, timing, actual app player and save handoff.
Headless validation never imports the app's running loop or writes real saves.
"""
import ast
from collections import Counter
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))
from engine.core import pin_wall as _pin_wall,unpin_wall as _unpin_wall  # RPE6 B-001
import pygame
from core.fsm import GameState,GameStateManager
from core import config
from cutscenes.engine import draw_cutscene_scene
from cutscenes import m5shadow3d as film
from missions.m5.finale_script import FINAL_SHOT,LINES,CUES,DURATION_MS

class Harness:
    """Execute the production classes; only OS/audio/global boundaries stubbed."""
    def __init__(self):
        self.clock=0;self.audio_events=[];self.dialogue=[];self.ends=[];self.pauses=[]
        self.tick=pygame.time.get_ticks;pygame.time.get_ticks=lambda:self.clock;_pin_wall(ms=lambda:self.clock)
        from audio import voice
        self.real_voice=voice;self.play_line=voice.play_line
        voice.play_line=lambda who,text,radio=False:self.dialogue.append((self.clock,who,text,radio))
        tree=ast.parse((ROOT/'src/app.py').read_text(encoding='utf-8-sig'))
        names=('CutscenePlayer','_CutsceneState','_GameState_','_MissionCompleteState')
        nodes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name in names]
        aud=SimpleNamespace(play=lambda name,volume=1:self.audio_events.append((self.clock,name,volume)),
             stop=lambda n:None,duck_ambience=lambda **kw:None)
        gc=SimpleNamespace(reset_dialogue_slide=lambda:None,active_mission='MISSION5',draw_cutscene_scene=draw_cutscene_scene)
        self.env={'pygame':pygame,'GameState':GameState,'audio':aud,'gc':gc,'KO_CUT_CUES':{},'TEXT_SPEED':2,'_now_ms':lambda:self.clock,
          'voice':SimpleNamespace(stop=lambda:self.pauses.append('stop'),pause=lambda:self.pauses.append('pause'),resume=lambda:self.pauses.append('resume')),
          '_play_typewriter_tick':lambda *a,**k:None,'_set_ambience':lambda a:None,
          'gsm':SimpleNamespace(transition=self.ends.append),'trigger_transition':self.ends.append,
          'draw_letterbox':lambda s:(pygame.draw.rect(s,(0,0,0),(0,0,1000,80)),pygame.draw.rect(s,(0,0,0),(0,620,1000,80))),
          'draw_vignette':lambda *a,**k:None,'draw_scanlines':lambda *a:None,'_advance_grain':lambda:None,
          'WIDTH':1000,'HEIGHT':700,'mission_complete_timer':0,'mission_complete_fade':0}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'app.py','exec'),self.env)
        self.fresh()
    def fresh(self):
        self.audio_events.clear();self.dialogue.clear();self.ends.clear()
        self.cp=self.env['CutscenePlayer']([FINAL_SHOT],'MISSION5_COMPLETE',True)
        self.env['active_cutscene']=self.cp;self.state=self.env['_CutsceneState']();self.state.enter()
    def at(self,elapsed,update=True):
        self.clock=self.cp.start_time+elapsed
        if update:self.state.update(1/60)
    def key(self,key):self.state.handle_event(pygame.event.Event(pygame.KEYDOWN,key=key),0,0,{})
    def frame(self,elapsed):
        self.at(elapsed);s=pygame.Surface((1000,700));self.state.render(s);return s
    def close(self):
        pygame.time.get_ticks=self.tick;_unpin_wall();self.real_voice.play_line=self.play_line


def playback_check():
    h=Harness()
    try:
        h.clock=2500;h.state.enter();assert h.cp.elapsed_ms==0,'Transition consumed opening'
        h.at(9800);h.at(9800);assert len(h.dialogue)==1
        h.key(pygame.K_SPACE);assert not h.ends,'SPACE bypassed authored ending'
        h.key(pygame.K_ESCAPE);frozen=h.cp.elapsed_ms
        h.clock+=30000;h.state.update(1/60);assert h.cp.elapsed_ms==frozen and len(h.dialogue)==1
        h.key(pygame.K_ESCAPE);assert not h.cp.paused and h.cp.elapsed_ms==frozen
        h.at(9900);assert len(h.dialogue)==1,'Replay after pause'
        h.key(pygame.K_RETURN);assert h.cp.skip_confirm and h.cp.paused and not h.ends
        h.key(pygame.K_ESCAPE);assert not h.cp.skip_confirm and not h.cp.paused
        h.at(DURATION_MS);h.state.update(1/60);h.state._handle_end();assert h.ends==['MISSION_COMPLETE']
        h.fresh();h.key(pygame.K_RETURN);h.key(pygame.K_RETURN);h.key(pygame.K_RETURN)
        assert h.cp.completed and h.ends==['MISSION_COMPLETE'],'Skip double completion'
        h.fresh()
        for ms in range(0,DURATION_MS+1,50):h.at(ms)
        assert h.ends==['MISSION_COMPLETE'] and len(h.dialogue)==len(LINES)
        assert Counter(n for _,n,_ in h.audio_events)==Counter(n for _,n,_ in CUES),'Missing/double timed cues'
        assert [(who,txt,radio) for _,who,txt,radio in h.dialogue]==[(who,txt,True) for _,_,who,txt in LINES]
        h.fresh();h.at(20000);assert not h.audio_events and not h.dialogue,'Stale audio backlog'
        h.at(20100);assert not h.audio_events and not h.dialogue
        # Production completion entry, temporary campaign only, once on skip.
        from core import save_system
        from core.state import STATE
        before=vars(STATE).copy();oldfile=save_system.SAVE_FILE
        try:
            with tempfile.TemporaryDirectory(prefix='m5_shadow_save_') as tmp:
                save_system.SAVE_FILE=str(Path(tmp)/'save.json')
                save_system.select_slot(1);save_system.start_new_campaign(1)
                STATE.active_mission='MISSION5';STATE.mission_end_time=123456
                calls=[]
                def save(*a,**kw):calls.append(a[0]);return save_system.save_mission_complete_record(*a,**kw)
                manager=GameStateManager()
                h.env.update(gsm=manager,STATE=STATE,save_system=SimpleNamespace(save_mission_complete_record=save),
                  _mission_report_data=lambda success:{'time_str':'02:03','rank':'A','score':85},_apply_equipped_look=lambda:None)
                h.fresh();manager.add(h.state);manager.add(h.env['_MissionCompleteState']());manager.transition('CUTSCENE')
                h.key(pygame.K_RETURN);h.key(pygame.K_RETURN);h.state._handle_end()
                assert calls==['MISSION5'] and manager.current_name=='MISSION_COMPLETE'
                assert save_system.get_slot(1)['flags']['mission5_complete']
        finally:
            save_system.SAVE_FILE=oldfile;vars(STATE).clear();vars(STATE).update(before)
    finally:h.close()
    print('PASS: production clock, timed dialogue/cues, pause, cancel/confirmed skip, completion save once')


def geometry_check():
    from engine3d import v_add,v_sub,m_apply
    b,u,m=film.actors();worst=0
    def contact(hum,p):
        # Support hand on the weapon's own foregrip (instance fit, rifle frame).
        _,j,R,_=hum.placements(p)
        target=v_add(j['rhand'],m_apply(R,hum._foregrip))
        return sum(x*x for x in v_sub(target,j['lhand']))**.5
    for hum in (b,u):
        assert hum._foregrip[2]>0 and hum._stock>0,'Weapon fit missing'
        for ms in range(0,DURATION_MS+1,100):
            st=film.state_at(ms);p=film.armed_pose(hum,ms,st['lower'] if hum is u else .40)
            err=contact(hum,p);worst=max(worst,err)
            assert err<.002,('Support hand detached',ms,err)
        # The live film also aims and lowers: the solver must hold contact and
        # never throw across the whole envelope (the 16:04 crash was a throw).
        for lower in (0,.25,.5,.75,1):
            for yaw in (-55,-30,0,20):
                for pitch in (-25,0,30):
                    p=film.armed_pose(hum,0,lower,aim=(yaw,pitch),look=(yaw,pitch))
                    err=contact(hum,p);worst=max(worst,err)
                    assert err<.002,('Support hand detached (aim)',lower,yaw,pitch,err)
    # A stance foot stays planted even on shorter/taller canonical cast rigs.
    # The first stride of the exit route is straight, so the pose applied along
    # a straight line must keep the left foot fixed for the whole stance phase.
    stance=film.STANCE*film.UC_STRIDE
    for hum in (m,u):
        anchor=[]
        for f in (.05,.2,.35,.5,.65,.8,.97):
            distance=stance*f
            pose=film.walking_pose(distance,0,True,hum._scale)
            places,_,root=hum.pose_world(pose,(-distance,0,0),-90,False)
            org=next(org for slot,key,M,org,g,fb in places if slot==9)
            anchor.append(v_add(root,org))
        assert max(abs(p[0]-anchor[0][0]) for p in anchor)<.00001,'Sliding stance foot'
        assert max(abs(p[2]-anchor[0][2]) for p in anchor)<.002,'Sliding stance foot (lateral)'
    # Roof-column clearance for body AND the long rifle, through intermediate poses.
    for ms in range(32800,34801,50):
        st=film.state_at(ms);p=film.armed_pose(u,ms,1)
        walk=film.walking_pose(st['uc_distance'],ms,scale=u._scale)
        for n in ('lhip_p','rhip_p','lkn','rkn'):p[n]=walk[n]
        places,_,root=u.pose_world(p,st['uc_pos'],st['uc_yaw'])
        for slot,key,M,org,g,fb in places:
            verts=u._rifle.verts if key=='rifle' else u._parts[key][0]
            world=(v_add(root,v_add(org,m_apply(M,v))) for v in verts)
            assert not any(1.05<x<1.75 and 5<y<8 and 26.85<z<27.65 for x,y,z in world),('Column clipping',ms,key)
    r,_=film._renderer(True)
    # Head-safe framing on every coverage beat; the subject is whoever the
    # camera covers. The withdrawal follows Ucilev down to the landing
    # (UC_RETREAT_END), then tilts up to the entrance while he stays below it.
    for ms in (6200,8500,12400,13900,15500,19500,24500,26700,30900,32200,34900,36400,38200,41000):
        st=film.state_at(ms);eye,target,fov,view=film._camera(ms);r.set_camera(eye,target,fov)
        hum=u if view in ('ucilev','withdrawal') else b
        if view=='withdrawal':assert ms<=film.UC_RETREAT_END,('Sample after the tilt-up',ms)
        pose=film.armed_pose(hum,ms,st['lower'] if hum is u else .40)
        pos,yaw=(st['uc_pos'],st['uc_yaw']) if hum is u else (film.BIRI,st['biri_yaw'])
        places,_,root=hum.pose_world(pose,pos,yaw)
        M,org=next((M,org) for slot,key,M,org,g,fb in places if slot==2)
        pixels=[r.project(v_add(root,v_add(org,m_apply(M,v)))) for v in hum._parts['head'][0]]
        assert all(pt is not None and 8<pt[1]<film.RH-10 and 0<pt[0]<film.RW for pt in pixels),('Cropped head',ms,view)
    assert not film.state_at(9599)['uc_visible'] and film.state_at(9600)['uc_visible']
    # Two-stage lowering: a tenth on "Not tonight", the rest once the dot is
    # off him, complete before he turns away; monotonic in between.
    assert film.state_at(film.LOWER_DIP[0])['lower']==0 and film.state_at(sum(film.LOWER_DROP))['lower']==1
    assert sum(film.LOWER_DROP)<=31700,'Lowering runs into the turn'
    seq=[film.state_at(ms)['lower'] for ms in range(26700,31700,50)]
    assert all(a<=b for a,b in zip(seq,seq[1:])),'Lowering not monotonic'
    assert film.state_at(42000)==film.state_at(99999)
    assert film.state_at(0)==film.state_at(-1)
    src=(ROOT/'src/cutscenes/m5shadow3d.py').read_text()
    parsed=ast.parse(src)
    imports=[n.module for n in ast.walk(parsed) if isinstance(n,ast.ImportFrom)]
    assert not any('m5ending' in (n or '') or 'm5martial' in (n or '') for n in imports)
    from audio.voice_manifest import VOICE_LINES,KNOWN_MISSING_AUDIO
    for idx,(_,_,who,txt) in enumerate(LINES,192):
        assert (f'VO_{idx}',who,txt) in VOICE_LINES
    print(f'PASS: all lowering frames solve both hands (worst contact error {worst*1000:.3f} mm); reveal ordering; no legacy finale imports')


def render_check():
    import numpy as np
    from core.state import STATE
    before=getattr(STATE,'reduced_motion',False);STATE.reduced_motion=True
    samples=(0,1500,4500,6200,7800,9599,9600,10700,12400,15500,19500,24500,28000,29700,30900,32500,33800,34800,37000,41000)
    s=pygame.Surface((1000,700));times=[]
    try:
        for ms in samples:
            s.fill((9,11,13));now=time.perf_counter();film.draw(s,ms,True);times.append((time.perf_counter()-now)*1000)
            px=pygame.surfarray.array3d(s)[:,80:556,:];assert np.std(px)>7,(ms,'Flat frame')
            assert s.get_at((25,650))[:3]==(9,11,13),'Renderer escaped film bounds'
        film.draw(s,19500,True);a=pygame.image.tobytes(s,'RGB')
        film.draw(s,1500,True);film.draw(s,19500,True);assert a==pygame.image.tobytes(s,'RGB'),'Non-deterministic seek'
        film.draw(s,42000,True);a=pygame.image.tobytes(s,'RGB');film.draw(s,99999,True);assert a==pygame.image.tobytes(s,'RGB')
    finally:STATE.reduced_motion=before
    print(f'PASS: every camera and 3D software fallback; deterministic seek; median render {sorted(times)[len(times)//2]:.1f} ms')


def shell_check():
    """No below-horizon ray may see past the world shell. A miss is only allowed
    inside the fog-convergence band: rays shallower than 1.4 deg land beyond the
    shell rim, where the sky and fully fogged geometry are the same tone."""
    import math
    from cutscenes import m5harbour_art as art
    r,_=film._renderer(True)
    seal=list(art.SHELL_SEAL)
    walls=list(art.SHELL_WALLS)
    samples=(1000,3000,6100,7000,9000,10000,11000,12500,13500,14500,16000,18000,
             22000,25000,27000,30000,32000,33500,34500,35500,38000,41500)
    tested=0;misses=[]
    for ms in samples:
        eye,target,fov,view=film._camera(ms)
        r.set_camera(eye,target,fov)
        hz=int(round(r.horizon_y()))
        for sy in range(max(0,hz+3),film.RH,7):
            for sx in range(0,film.RW,16):
                d=[r.fwd[i]+r.right[i]*((sx-film.RW/2)/r.focal)+r.up[i]*((film.RH/2-sy)/r.focal) for i in range(3)]
                n=math.sqrt(sum(c*c for c in d));d=[c/n for c in d]
                if d[1]>=-1e-9:continue
                tested+=1
                for x0,z0,x1,z1,oy in seal:
                    tt=(oy-r.cam[1])/d[1]
                    if tt<=0:continue
                    px=r.cam[0]+d[0]*tt;pz=r.cam[2]+d[2]*tt
                    if x0<=px<=x1 and z0<=pz<=z1:break
                else:
                    for wz,wx0,wx1,wy0,wy1 in walls:
                        if abs(d[2])<1e-9:continue
                        tt=(wz-r.cam[2])/d[2]
                        if tt<=0:continue
                        px=r.cam[0]+d[0]*tt;py=r.cam[1]+d[1]*tt
                        if wx0<=px<=wx1 and wy0<=py<=wy1:break
                    else:
                        dep=-math.degrees(math.asin(d[1]))
                        if dep>1.4:misses.append((ms,view,sx,sy,round(dep,2)))
    assert not misses,f'World shell leaks: {misses[:6]} of {tested} rays'
    print(f'PASS: {tested} below-horizon rays sealed by the world shell across {len(samples)} beats')


def sky_and_frame_check():
    import numpy as np
    r,buf=film._renderer(True)
    eye,target,fov,view=film._camera(1000);r.set_camera(eye,target,fov)
    film._sky(buf,r,0)
    hz=int(round(r.horizon_y()))
    fog=tuple(int(v) for v in r.fog)
    assert buf.get_at((film.RW//2,hz))[:3]==fog,'Horizon tone does not match the fog'
    prev=None
    for y in range(hz+1,film.RH):
        c=buf.get_at((film.RW//2,y))[:3]
        assert all(fog[i]-6<=c[i]<=fog[i] for i in range(3)),('Below-horizon sky left the fog band',y,c)
        if prev is not None:assert all(c[i]<=prev[i] for i in range(3)),('Below-horizon sky brightens',y,c)
        prev=c
    s=pygame.Surface((1000,700));s.fill((0,0,0))
    from cutscenes.engine import reset_dialogue_slide
    reset_dialogue_slide()
    film._subtitle(s,12400)
    rows=np.where(pygame.surfarray.array3d(s).any(axis=0).any(axis=1))[0]
    # Cinematic subtitle bar spans the bottom of the frame (letterbox band).
    # 12400 is the UCILEV line, rendered in the centered cinematic bar.
    assert len(rows) and 600<=rows[0] and rows[-1]<=700, ('Finale subtitle not in the cinematic bottom bar',rows[0] if len(rows) else None,rows[-1] if len(rows) else None)
    film.draw(s,33000,True)
    a=pygame.surfarray.array3d(s)
    for y in list(range(80,112))+list(range(589,620)):
        assert not a[:,y,:].any(),('Letterbox band not black',y)
    print('PASS: horizon equals fog, below-horizon gradient stays in the fog band, subtitle in the shared dialogue box, symmetric black bars')


def check():
    pygame.init();geometry_check();shell_check();render_check();sky_and_frame_check();playback_check()
    from m5_finale_cut_check import check as fallback
    fallback()
    print('M5 SHADOW FINALE: OK')
if __name__=='__main__':check()
