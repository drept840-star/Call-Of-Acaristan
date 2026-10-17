"""Headless regression checks and optional preview for the K-9 pickup.
Run from the project root: python tools/k9_pickup_check.py [--frames DIR]
The playback harness executes the existing app classes without launching app.
"""
import argparse
import ast
from collections import Counter
import os
from pathlib import Path
import random
import sys
import time
from types import SimpleNamespace

os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))
import pygame
from cutscenes import k9, m3ops
from cutscenes.engine import draw_cutscene_scene
from core.config import WIDTH,HEIGHT,SCENE_TOP,SCENE_BOT,audio
from missions.m3.meta import k9_pickup_shots


def render(fn,ms):
    s=pygame.Surface((WIDTH,HEIGHT));s.fill((5,5,8));fn(s,ms);return s


def rgb(s):return pygame.image.tobytes(s,'RGB')


def playback_check():
    # Use the actual production update/input logic, not a parallel simulation.
    tree=ast.parse((ROOT/'src/app.py').read_text(encoding='utf-8-sig'))
    classes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name in ('CutscenePlayer','_CutsceneState')]
    clock=[0];heard=[];ends=[];transitions=[]
    old_ticks=pygame.time.get_ticks
    pygame.time.get_ticks=lambda:clock[0]
    from engine.core import pin_wall,unpin_wall   # RPE6 B-001: game code reads the engine clock
    pin_wall(ms=lambda:clock[0])
    class StubAudio:
        def play(self,name,volume=1):heard.append((name,volume))
        def duck_ambience(self,**kw):pass
    gc=SimpleNamespace(reset_dialogue_slide=lambda:None,active_mission='MISSION3')
    env={'pygame':pygame,'GameState':object,'audio':StubAudio(),'gc':gc,'_now_ms':lambda:clock[0],
         'KO_CUT_CUES':{},'TEXT_SPEED':2,'_play_typewriter_tick':lambda *a,**k:None,
         'trigger_transition':transitions.append}
    try:
        exec(compile(ast.Module(body=classes,type_ignores=[]),str(ROOT/'src/app.py'),'exec'),env)
        cp=env['CutscenePlayer'](k9_pickup_shots,'GAME',use_fades=True)
        env['active_cutscene']=cp
        state=env['_CutsceneState']()
        real_end=state._handle_end
        def end():
            real_end();ends.append(clock[0])
        state._handle_end=end
        # Early held/tapped SPACE must not clip the action or emit menu clicks.
        state.handle_event(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE),0,0,{})
        assert cp.shot_idx==0 and not heard
        for now in range(0,5201,10):
            clock[0]=now;state.update(1/100)
            if ends:break
        assert ends and 4800<=ends[0]<=4830,ends
        assert transitions==['GAME'],transitions
        expected=[(name,vol) for shot in k9_pickup_shots for _,name,vol in shot.get('cues',())]
        assert heard==expected,(heard,expected)
        assert cp.transition_timer==0,'Unexpected shot fade'
        # A suspended window must consume stale cues, not blast a backlog.
        heard.clear();clock[0]=0
        cp=env['CutscenePlayer'](k9_pickup_shots,'GAME',use_fades=True)
        cp.shot_idx=1;env['active_cutscene']=cp
        clock[0]=2000;state.update(1/60)
        assert heard==[('rifle_handle',.18)],heard
        state.update(1/60)
        assert heard==[('rifle_handle',.18)],'Cue repeated'
    finally:pygame.time.get_ticks=old_ticks;unpin_wall()
    print('PASS: actual player auto-completes, returns to GAME, one-shot cues, early SPACE and stale cues')


def checks():
    assert [s['min_ms'] for s in k9_pickup_shots]==[k9.WALL_MS,k9.GRAB_MS,k9.READY_MS]
    for shot in k9_pickup_shots:
        assert all(shot.get(k) for k in ('quiet_ui','auto_advance','hide_caption','hard_cut'))
        for ms,name,vol in shot.get('cues',()):
            assert 0<=ms<shot['min_ms'] and 0<vol<=1
            assert audio.get_sound(name) is not None,name
    fns=[m3ops._draw_k9_wall_stand,m3ops._draw_k9_firstperson_grab,m3ops._draw_k9_ready_check]
    durations=[k9.WALL_MS,k9.GRAB_MS,k9.READY_MS]
    for i in range(2):
        assert rgb(render(fns[i],durations[i]))==rgb(render(fns[i+1],0)),'Discontinuous cut'
    print('PASS: exact pixel continuity at both shot boundaries and valid sound cues')
    state=random.getstate()
    for fn,dur in zip(fns,durations):
        for ms in (-1,0,dur*.25,dur*.5,dur*.75,dur,dur+300):
            first=render(fn,ms)
            assert rgb(first)==rgb(render(fn,ms)),'Non-deterministic frame'
            assert rgb(first.subsurface((0,0,WIDTH,SCENE_TOP)))==bytes((5,5,8))*(WIDTH*SCENE_TOP)
            assert rgb(first.subsurface((0,SCENE_BOT,WIDTH,HEIGHT-SCENE_BOT)))==bytes((5,5,8))*(WIDTH*(HEIGHT-SCENE_BOT))
    assert state==random.getstate(),'Global RNG mutated'
    clip=pygame.Rect(40,120,180,100);s=pygame.Surface((WIDTH,HEIGHT));s.fill((255,0,255));s.set_clip(clip)
    k9.draw_ready(s,800)
    assert s.get_clip()==clip and s.get_at((500,400))[:3]==(255,0,255)
    print('PASS: deterministic rendering, safe out-of-range clocks, clip restoration and protected letterbox')
    # Both fingers are at their rigid contact before the gun moves.
    pose=k9._pose(k9.WALL_MS+560)
    assert pose==k9._pose(0)
    d,s,pull=k9._hands(k9.WALL_MS+560,pose)
    assert d[2]==s[2]==1 and len((d,s))==2
    print('PASS: two hands reach contact before rack release')
    playback_check()
    timings=[]
    for ms in range(0,k9.TOTAL_MS,20):
        s=pygame.Surface((WIDTH,HEIGHT));start=time.perf_counter();k9._draw(s,ms);timings.append((time.perf_counter()-start)*1000)
    timings.sort()
    print(f'Render cost: median {timings[len(timings)//2]:.2f} ms, p95 {timings[int(len(timings)*.95)]:.2f} ms; transform cache capped at {k9._weapon_transform.cache_info().maxsize} frames')
    print('K9 CHECK: OK')


def frames(directory):
    from core.config import draw_vignette
    directory.mkdir(parents=True,exist_ok=True)
    shot_idx=0;offset=0
    for frame in range(round(k9.TOTAL_MS/1000*60)):
        ms=frame*1000/60
        while shot_idx<2 and ms>=offset+k9_pickup_shots[shot_idx]['min_ms']:
            offset+=k9_pickup_shots[shot_idx]['min_ms'];shot_idx+=1
        s=pygame.Surface((WIDTH,HEIGHT))
        draw_cutscene_scene(s,k9_pickup_shots[shot_idx],ms-offset)
        draw_vignette(s,strength=80)
        pygame.draw.rect(s,(5,5,8),(0,0,WIDTH,SCENE_TOP))
        pygame.draw.rect(s,(5,5,8),(0,SCENE_BOT,WIDTH,HEIGHT-SCENE_BOT))
        pygame.image.save(s,directory/f'{frame:04d}.png')
    print('Rendered preview frames:',frame+1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--frames',type=Path);args=parser.parse_args()
    checks()
    if args.frames:frames(args.frames)
    pygame.quit()
